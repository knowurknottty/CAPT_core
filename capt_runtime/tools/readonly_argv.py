"""Fail-closed read-only admission for explicit argv commands.

Ported from OpenWorker ``coworker/readonly.py`` (MIT, (c) 2024 Andrew Ng,
https://github.com/andrewyng/openworker @ e947e44) and re-designed for CAPT's
argv-only terminal contract. Differences from upstream, each a closed bug class:

* argv only: no shell grammar, pipelines, substitutions or env assignments to
  parse. A pipeline is several governed calls, not one admitted string.
* ``uniq IN OUT`` writes OUT; upstream admitted it. Here: at most one operand.
* ``actionlint -shellcheck=PATH`` executes PATH; upstream admitted it. Dropped.
* ``git status|diff|log -p|show|blame|grep`` execute repository-configured
  programs (core.fsmonitor, filter.*.clean, diff.external, diff.*.textconv,
  core.hooksPath/post-index-change, gpg.program). Upstream admitted them as
  reads. Here every git invocation is rewritten with neutralizing ``-c``
  overrides and flags, and commands that may run clean/smudge filters require
  a configured-driver probe (``git_filter_driver_names``) before execution.
* Values of file-reading flags (``grep -f``, ``jq --rawfile``) are read
  targets, so scope checks see them.

The verdict is advisory to nobody: ``admit`` either returns an executable plan
or raises ``ReadOnlyRefused``. A refusal costs one governed approval; a false
admission costs an unreviewed effect. Every ambiguity refuses.

This module never spawns processes. ``git_filter_driver_names`` parses the
output of a probe the adapter runs with ``GIT_PROBE_ARGV``.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.scope import require_scoped_path

POLICY_VERSION = "readonly-argv-v1"


class ReadOnlyRefused(AuthorityViolation):
    """The argv is not provably a local read; route it through approval."""


@dataclass(frozen=True)
class ReadOnlyPlan:
    argv: tuple[str, ...]  # hardened argv to execute
    env_overrides: tuple[tuple[str, str], ...]
    read_targets: tuple[str, ...]  # raw operands, scope-check before exec
    needs_filter_probe: bool  # run GIT_PROBE_ARGV, then finalize_git_argv
    policy_version: str = POLICY_VERSION


# -- non-git verbs ------------------------------------------------------------

# verb -> denied flags. A token matches the flag exactly, as `--long=value`, or
# (short flags) attached or inside a cluster.
_SIMPLE: dict = {
    "ls": ("-L", "-R", "--dereference", "--recursive", "--dereference-command-line", "--dereference-command-line-symlink-to-dir"), "cat": (), "head": (), "wc": (), "nl": (), "cut": (),
    "stat": (), "df": (), "pwd": (), "whoami": (), "id": (), "uname": (),
    "basename": (), "dirname": (), "realpath": (), "readlink": (),
    "which": (), "cmp": (), "comm": (), "strings": (), "od": (), "hexdump": (),
    "md5sum": (), "sha1sum": (), "sha256sum": (), "sha512sum": (), "shasum": (),
    "diff": ("--no-index",),
    "tail": ("-f", "-F", "--follow", "--retry"),  # follow never terminates
    "uniq": (),  # operand count policed below
    "xxd": ("-r",),  # operand count policed below
    "date": ("-s", "--set"),
    "file": ("-C", "--compile"),
    "du": ("--files0-from", "-L", "-H", "-D", "--dereference", "--dereference-args", "-X", "--exclude-from"),
    "grep": ("-R", "--dereference-recursive"), "egrep": ("-R", "--dereference-recursive"), "fgrep": ("-R", "--dereference-recursive"),
    "rg": ("--pre", "--pre-glob", "-z", "--search-zip", "--hostname-bin", "-L", "--follow"),
    "find": (),  # policed below
}

# Flags whose VALUE is a file the command reads.
_PATH_VALUE_FLAGS = {
    "grep": ("-f", "--file", "--exclude-from"),
    "egrep": ("-f", "--file"),
    "fgrep": ("-f", "--file"),
    "rg": ("-f", "--file", "--ignore-file"),
    "file": ("-m", "--magic-file"),
    "date": ("-f", "--file"),
    "jq": ("-f", "--from-file"),
    "diff": ("--from-file", "--to-file"),
}
_PATTERN_FIRST = {"grep", "egrep", "fgrep", "rg", "jq"}
_NO_PATH_OPERANDS = {"pwd", "whoami", "id", "uname", "basename", "dirname", "date", "which"}
_FIND_DENY = (
    "-exec", "-execdir", "-ok", "-okdir", "-delete", "-L", "-H",
    "-fprint", "-fprint0", "-fprintf", "-fls",
)
_FIND_GLOBAL = {"-H", "-L", "-P", "-O0", "-O1", "-O2", "-O3"}


def _flag_hit(token: str, denied: Sequence[str]) -> bool:
    if not token.startswith("-") or token in {"-", "--"}:
        return False
    for flag in denied:
        if token == flag:
            return True
        if flag.startswith("--"):
            if token.startswith(flag + "="):
                return True
        elif len(flag) == 2 and not token.startswith("--") and flag[1] in token[1:]:
            return True
    return False


def _refuse(reason: str) -> ReadOnlyRefused:
    return ReadOnlyRefused("READONLY_REFUSED:" + reason)


def _flag_values(verb: str, args: Sequence[str]) -> tuple[list, set]:
    """(file values of path-valued flags, indexes consumed as flag values)."""
    flags = _PATH_VALUE_FLAGS.get(verb, ())
    values: list = []
    consumed: set = set()
    i = 0
    while i < len(args):
        tok = args[i]
        if verb == "jq" and tok in {"--rawfile", "--slurpfile"}:
            if i + 2 >= len(args):
                raise _refuse(f"{verb}:{tok}:missing-operands")
            values.append(args[i + 2])
            consumed.update({i, i + 1, i + 2})
            i += 3
            continue
        if verb == "jq" and tok in {"--arg", "--argjson"}:
            consumed.update({i, i + 1, i + 2})
            i += 3
            continue
        for flag in flags:
            if tok == flag:
                if i + 1 >= len(args):
                    raise _refuse(f"{verb}:{flag}:missing-value")
                values.append(args[i + 1])
                consumed.update({i, i + 1})
                i += 1
                break
            if flag.startswith("--") and tok.startswith(flag + "="):
                values.append(tok.split("=", 1)[1])
                consumed.add(i)
                break
            if len(flag) == 2 and not flag.startswith("--") and tok.startswith(flag) and len(tok) > 2:
                values.append(tok[2:])
                consumed.add(i)
                break
        i += 1
    return values, consumed


def _simple_plan(verb: str, args: Sequence[str]) -> ReadOnlyPlan:
    denied = _SIMPLE[verb]
    if any(_flag_hit(t, denied) for t in args):
        raise _refuse(f"{verb}:denied-flag")
    if verb == "find":
        return _find_plan(args)
    flag_files, consumed = _flag_values(verb, args)
    operands = [a for idx, a in enumerate(args) if idx not in consumed and (a == "-" or not a.startswith("-"))]
    if verb in {"uniq", "xxd"} and len(operands) > 1:
        raise _refuse(f"{verb}:second-operand-is-an-output-file")
    if verb in _NO_PATH_OPERANDS:
        operands = []
    elif verb in _PATTERN_FIRST and not any(
        _flag_hit(t, ("-e", "--regexp", "-f", "--file")) for t in args
    ) and operands:
        operands = operands[1:]  # first positional is the pattern / jq program
    operands = [o for o in operands if o != "-"]
    return ReadOnlyPlan(
        argv=(verb, *args),
        env_overrides=(("LC_ALL", "C"),),
        read_targets=tuple(flag_files + operands),
        needs_filter_probe=False,
    )


def _find_plan(args: Sequence[str]) -> ReadOnlyPlan:
    if any(_flag_hit(t, _FIND_DENY) for t in args):
        raise _refuse("find:exec-or-write-predicate")
    if any(t.startswith("-files0-from") for t in args):
        raise _refuse("find:files0-from")
    i = 0
    while i < len(args) and args[i] in _FIND_GLOBAL:
        i += 1
    starts = []
    while i < len(args) and not args[i].startswith(("-", "(", "!", ")")):
        starts.append(args[i])
        i += 1
    return ReadOnlyPlan(
        argv=("find", *args), env_overrides=(("LC_ALL", "C"),),
        read_targets=tuple(starts or ["."]), needs_filter_probe=False,
    )


# -- git ----------------------------------------------------------------------

# Overrides placed before the subcommand. Command-line -c beats repo config.
GIT_HARDENING = (
    "-c", "core.fsmonitor=false",
    "-c", "core.hooksPath=/dev/null",
    "-c", "core.pager=cat",
    "-c", "core.sshCommand=false",
    "-c", "diff.external=",
    "-c", "log.showSignature=false",
    "-c", "gpg.program=false",
    "-c", "gpg.ssh.program=false",
    "-c", "gpg.x509.program=false",
    "-c", "protocol.allow=never",
    "--no-pager",
    "--no-optional-locks",
)
GIT_ENV = (
    ("GIT_CONFIG_NOSYSTEM", "1"),
    ("GIT_NO_LAZY_FETCH", "1"),  # git >= 2.44: no promisor fetch on object read
    ("GIT_TERMINAL_PROMPT", "0"),
    ("GIT_OPTIONAL_LOCKS", "0"),
    ("GIT_PAGER", "cat"),
    ("PAGER", "cat"),
    ("LC_ALL", "C"),
)
# Probe for configured filter drivers, run hardened in the same cwd.
GIT_PROBE_ARGV = ("git", *GIT_HARDENING, "config", "--null", "--name-only", "--get-regexp", r"^filter\.")

_GIT_PLAIN = {
    "rev-parse", "rev-list", "ls-files", "ls-tree", "name-rev", "merge-base",
    "count-objects", "describe", "shortlog",
}
_GIT_DIFFING = {"diff", "log", "show"}  # get --no-ext-diff --no-textconv
_GIT_FILTERING = {"status", "diff", "blame", "grep"}  # may run clean filters on the worktree
_GIT_DENY_ANY = (
    "--output", "--ext-diff", "--textconv", "--filters", "--show-signature",
    "--no-index", "-O", "--open-files-in-pager", "--paginate",
)
_GIT_BRANCH_OK = {
    "--show-current", "--list", "-a", "-r", "-v", "-vv", "--contains",
    "--merged", "--no-merged", "--all",
}
# blame only: these name files it reads (log -S is a pickaxe string, not a file).
_BLAME_FILE_FLAGS = ("--contents", "-S", "--ignore-revs-file")


def _git_plan(args: Sequence[str]) -> ReadOnlyPlan:
    targets: list = []
    i = 0
    while i < len(args):
        if args[i] == "-C" and i + 1 < len(args):
            targets.append(args[i + 1])
            i += 2
            continue
        if args[i] == "--no-pager":
            i += 1
            continue
        break
    if i >= len(args):
        raise _refuse("git:no-subcommand")
    sub, rest = args[i], list(args[i + 1:])
    if sub.startswith("-"):
        raise _refuse("git:global-flag")  # -c, --config-env, --git-dir, --exec-path ...
    if any(_flag_hit(t, _GIT_DENY_ANY) for t in rest):
        raise _refuse(f"git-{sub}:denied-flag")
    if sub == "cat-file" and not any(t in {"-t", "-s", "-e", "-p", "--batch-check"} for t in rest):
        raise _refuse("git-cat-file:mode")
    ok = (
        sub in _GIT_PLAIN or sub in _GIT_DIFFING or sub in _GIT_FILTERING or sub == "cat-file"
        or (sub == "branch" and all(t in _GIT_BRANCH_OK or t.startswith(("--format=", "--sort=")) for t in rest))
        or (sub == "tag" and bool(rest) and all(t in {"-l", "--list", "--contains", "--merged"} or t.startswith("-n") for t in rest))
        or (sub == "stash" and bool(rest) and rest[0] in {"list", "show"})
        or (sub == "remote" and (not rest or rest[0] in {"-v", "get-url"}))
        or (sub == "reflog" and (not rest or rest[0] == "show"))
        or (sub == "config" and any(t in {"--get", "--get-all", "--get-regexp", "--list", "-l"} for t in rest)
            and not any(t.startswith(("--add", "--unset", "--replace", "--rename", "--remove", "--edit", "-e")) for t in rest))
    )
    if not ok:
        raise _refuse(f"git-{sub}:not-a-read")
    for idx, tok in enumerate(rest if sub == "blame" else ()):
        for flag in _BLAME_FILE_FLAGS:
            if tok == flag and idx + 1 < len(rest):
                targets.append(rest[idx + 1])
            elif flag.startswith("--") and tok.startswith(flag + "="):
                targets.append(tok.split("=", 1)[1])
    tail: list = []
    if sub in _GIT_DIFFING:
        tail = ["--no-ext-diff", "--no-textconv"]
    elif sub in {"blame", "grep"}:
        tail = ["--no-textconv"]
    # Insert hardening flags right after the subcommand, before any "--".
    hardened = ("git", *GIT_HARDENING, *args[:i], sub, *tail, *rest)
    return ReadOnlyPlan(
        argv=hardened, env_overrides=GIT_ENV, read_targets=tuple(targets),
        needs_filter_probe=sub in _GIT_FILTERING,
    )


_DRIVER_KEY = re.compile(r"^filter\.(.+)\.(clean|smudge|process|required)$")


def git_filter_driver_names(probe_stdout: bytes) -> tuple[str, ...]:
    """Parse NUL-separated `git config --name-only` output into driver names."""
    names = []
    for raw in probe_stdout.split(b"\0"):
        key = raw.decode("utf-8", "strict").strip().lower()
        if not key:
            continue
        match = _DRIVER_KEY.match(key)
        if match is None:
            continue  # other filter.* keys carry no program
        name = match.group(1)
        if not name or any(ch in name for ch in "\n\r\0="):
            raise _refuse("git:unrepresentable-filter-driver")
        if name not in names:
            names.append(name)
    return tuple(names)


def finalize_git_argv(plan: ReadOnlyPlan, driver_names: Iterable[str]) -> tuple[str, ...]:
    """Neutralize every configured filter driver for a worktree-reading git call."""
    if not plan.needs_filter_probe:
        return plan.argv
    overrides: list = []
    for name in driver_names:
        for key in ("clean", "smudge", "process"):
            overrides += ["-c", f"filter.{name}.{key}="]
        overrides += ["-c", f"filter.{name}.required=false"]
    return (plan.argv[0], *overrides, *plan.argv[1:])


# -- entry points ---------------------------------------------------------------


def admit(argv: Sequence[str]) -> ReadOnlyPlan:
    """Return an execution plan for a provably-local-read argv, or raise."""
    if not isinstance(argv, (list, tuple)) or not argv:
        raise _refuse("empty")
    if not all(isinstance(a, str) and a and "\0" not in a for a in argv):
        raise _refuse("malformed-argv")
    verb = argv[0]
    if "/" in verb or os.sep in verb:
        raise _refuse("path-invoked-binary")
    if verb == "git":
        return _git_plan(argv[1:])
    if verb in _SIMPLE:
        return _simple_plan(verb, argv[1:])
    raise _refuse(f"unknown-verb:{verb}")


def require_targets_in_scope(plan: ReadOnlyPlan, root: Path, cwd: Path) -> tuple[Path, ...]:
    """Resolve every read target against cwd and require it inside root.

    Missing targets refuse (require_scoped_path is strict), so a later-created
    symlink cannot redirect a read that was scope-checked as absent.
    """
    resolved = []
    for target in plan.read_targets:
        candidate = Path(target).expanduser()
        if not candidate.is_absolute():
            candidate = Path(cwd) / candidate
        resolved.append(require_scoped_path(root, candidate))
    return tuple(resolved)
