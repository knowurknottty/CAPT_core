from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.readonly_argv import (
    GIT_PROBE_ARGV,
    ReadOnlyRefused,
    admit,
    finalize_git_argv,
    git_filter_driver_names,
    require_targets_in_scope,
)


@pytest.mark.parametrize("argv", [
    ["ls", "-la", "src"],
    ["cat", "README.md"],
    ["grep", "-rn", "TODO", "src"],
    ["rg", "-n", "retry", "capt_runtime"],
    ["uniq", "-c", "a.txt"],
    ["find", ".", "-name", "*.py", "-newer", "x"],
    ["git", "status"],
    ["git", "log", "--oneline", "-5"],
    ["git", "-C", "sub", "diff", "HEAD~1"],
    ["git", "branch", "--show-current"],
    ["git", "config", "--get", "remote.origin.url"],
])
def test_admits_local_reads(argv):
    plan = admit(argv)
    assert plan.argv[0] == argv[0]


@pytest.mark.parametrize("argv,why", [
    (["uniq", "in.txt", "out.txt"], "uniq writes its second operand (OpenWorker admits this)"),
    (["xxd", "a", "b"], "xxd writes its second operand"),
    (["actionlint", "-shellcheck=/tmp/evil"], "executes an arbitrary binary (OpenWorker admits this)"),
    (["sort", "-o", "x", "y"], "write"),
    (["sort", "-ro", "x", "y"], "write hidden in cluster"),
    (["sort", "--output=x", "y"], "write"),
    (["rg", "--pre", "sh", "x"], "exec"),
    (["rg", "-z", "x"], "spawns decompressors"),
    (["find", ".", "-exec", "rm", "{}", "+"], "exec"),
    (["find", ".", "-fprint", "/tmp/x"], "write"),
    (["tail", "-f", "log"], "never terminates"),
    (["date", "-s", "2020-01-01"], "sets clock"),
    (["/usr/bin/cat", "x"], "path-invoked binary"),
    (["python3", "-c", "print(1)"], "interpreter"),
    (["curl", "https://example.com"], "network"),
    (["git", "-c", "core.pager=sh", "log"], "user-supplied config"),
    (["git", "--git-dir=/tmp/x", "log"], "global flag"),
    (["git", "log", "--ext-diff", "-p"], "external diff"),
    (["git", "show", "--textconv", "HEAD:x"], "textconv"),
    (["git", "log", "--output=/tmp/x"], "write"),
    (["git", "log", "--show-signature"], "gpg.program"),
    (["git", "grep", "-Oless", "x"], "pager exec"),
    (["git", "diff", "--no-index", "/etc/passwd", "x"], "out-of-repo read"),
    (["git", "cat-file", "--filters", "HEAD:x"], "filter exec"),
    (["git", "commit", "-m", "x"], "write"),
    (["git", "config", "--add", "--get", "x"], "config write"),
    ([], "empty"),
    (["cat", "a\0b"], "NUL"),
])
def test_refuses(argv, why):
    with pytest.raises(ReadOnlyRefused):
        admit(argv)


def test_refusal_is_an_authority_violation():
    with pytest.raises(AuthorityViolation):
        admit(["rm", "-rf", "/"])


def test_flag_value_files_are_read_targets():
    assert "/etc/shadow" in admit(["grep", "--file=/etc/shadow", "x", "."]).read_targets
    assert "/etc/shadow" in admit(["grep", "-f", "/etc/shadow", "."]).read_targets
    plan = admit(["grep", "pattern", "a.txt"])
    assert plan.read_targets == ("a.txt",)  # pattern is not a path


def test_git_dir_flag_and_blame_files_are_targets():
    assert admit(["git", "-C", "/etc", "log"]).read_targets == ("/etc",)
    assert "/x/revs" in admit(["git", "blame", "--ignore-revs-file", "/x/revs", "f"]).read_targets
    assert admit(["git", "log", "-S", "needle"]).read_targets == ()  # pickaxe, not a file


def test_scope_check(tmp_path: Path):
    (tmp_path / "a.txt").write_text("x")
    plan = admit(["cat", "a.txt"])
    assert require_targets_in_scope(plan, tmp_path, tmp_path)
    with pytest.raises(AuthorityViolation):
        require_targets_in_scope(admit(["cat", "/etc/hostname"]), tmp_path, tmp_path)
    (tmp_path / "link").symlink_to("/etc")
    with pytest.raises(AuthorityViolation):
        require_targets_in_scope(admit(["ls", "link"]), tmp_path, tmp_path)


def test_git_hardening_is_always_present():
    plan = admit(["git", "diff"])
    joined = " ".join(plan.argv)
    for needle in ("core.fsmonitor=false", "core.hooksPath=/dev/null", "diff.external=",
                   "--no-ext-diff", "--no-textconv", "--no-optional-locks"):
        assert needle in joined
    assert plan.needs_filter_probe
    assert not admit(["git", "log", "-1"]).needs_filter_probe


def test_filter_probe_parsing():
    out = b"filter.lfs.clean\0filter.lfs.smudge\0filter.my.dot.name.process\0filter.x.unknown\0"
    assert git_filter_driver_names(out) == ("lfs", "my.dot.name")
    argv = finalize_git_argv(admit(["git", "status"]), ["lfs"])
    assert "filter.lfs.clean=" in argv and "filter.lfs.required=false" in argv


# -- end-to-end against a hostile repository ------------------------------------

@pytest.fixture
def hostile_repo(tmp_path: Path):
    if shutil.which("git") is None:
        pytest.skip("git not installed")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    sentinel = tmp_path / "pwned"

    def stub(name: str, body: str) -> Path:
        path = bin_dir / name
        path.write_text(f"#!/bin/sh\necho {name} >> '{sentinel}'\n{body}\n")
        path.chmod(0o755)
        return path

    fsmon = stub("fsmon", "exit 1")
    filt = stub("filt", "cat")
    tool = stub("tool", "true")
    textconv = stub("tc", 'cat "$1"')
    stub("post-index-change", "true")
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path), "GIT_CONFIG_NOSYSTEM": "1"}

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=repo, env=env, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "a@b")
    git("config", "user.name", "a")
    (repo / "f.txt").write_text("a\n")
    (repo / ".gitattributes").write_text("*.txt filter=f diff=d\n")
    git("add", ".")
    git("commit", "-qm", "one")
    git("config", "core.fsmonitor", str(fsmon))
    git("config", "filter.f.clean", f"{filt} clean")
    git("config", "diff.d.textconv", str(textconv))
    git("config", "diff.external", str(tool))
    git("config", "core.hooksPath", str(bin_dir))
    (repo / "f.txt").write_text("a\nb\n")
    return repo, env, sentinel


def _run(argv, repo, env):
    return subprocess.run(list(argv), cwd=repo, env=env, capture_output=True, timeout=20, check=False)


@pytest.mark.parametrize("argv", [
    ["git", "status"], ["git", "diff"], ["git", "log", "-p", "-1"],
    ["git", "show", "HEAD"], ["git", "blame", "f.txt"], ["git", "grep", "a"],
])
def test_raw_git_reads_execute_repo_programs(hostile_repo, argv):
    """Documents the bug class: these are NOT reads in a hostile repository."""
    repo, env, sentinel = hostile_repo
    _run(argv, repo, env)
    assert sentinel.exists(), f"expected {argv} to execute a repo-configured program"


@pytest.mark.parametrize("argv", [
    ["git", "status"], ["git", "diff"], ["git", "log", "-p", "-1"],
    ["git", "show", "HEAD"], ["git", "blame", "f.txt"], ["git", "grep", "a"],
])
def test_hardened_plans_execute_nothing(hostile_repo, argv):
    repo, env, sentinel = hostile_repo
    plan = admit(argv)
    run_env = {**env, **dict(plan.env_overrides)}
    final = plan.argv
    if plan.needs_filter_probe:
        probe = _run(GIT_PROBE_ARGV, repo, run_env)
        final = finalize_git_argv(plan, git_filter_driver_names(probe.stdout))
    result = _run(final, repo, run_env)
    assert result.returncode == 0, result.stderr.decode()
    assert not sentinel.exists(), sentinel.read_text()

@pytest.mark.parametrize("argv", [
    ["rg", "--follow", "canary", "."],
    ["rg", "-L", "canary", "."],
    ["rg", "--follow=true", "canary", "."],
])
def test_rg_follow_refuses_at_classifier_before_executable_resolution(argv):
    # This must reject even if /usr/bin/rg exists. Adapter-only refusal
    # can otherwise be a false positive from missing OS system executable.
    with pytest.raises(ReadOnlyRefused):
        admit(argv)

@pytest.mark.parametrize("argv", [
    ["sort", "--random-source=/tmp/outside", "data"],
    ["sort", "--temporary-directory=/tmp/outside", "data"],
    ["sort", "-T", "/tmp/outside", "data"],
    ["du", "--exclude-from=/tmp/outside", "."],
    ["du", "-X", "/tmp/outside", "."],
])
def test_indirect_file_inputs_and_temp_writes_are_not_readonly(argv):
    with pytest.raises(ReadOnlyRefused):
        admit(argv)

@pytest.mark.parametrize("argv", [
    ["jq", ".a", "data.json"],
    ["jq", "include \"private\"; .", "data.json"],
    ["jq", "--rawfile", "x", "/tmp/outside", ".", "data.json"],
])
def test_jq_unbounded_imports_are_not_readonly_argv(argv):
    # Don't advertise a safe admission through the reusable classifier
    # while the only current adapter rejects jq for implicit file imports.
    with pytest.raises(ReadOnlyRefused):
        admit(argv)

@pytest.mark.parametrize("argv", [
    ["sort", "big.csv"],
    ["sort", "-u", "big.csv"],
    ["sort", "--random-source=/tmp/outside", "big.csv"],
])
def test_sort_scratch_files_cannot_be_classified_as_pure_read(argv):
    # GNU/BSD sort can spill to TMPDIR regardless of explicit --output.
    with pytest.raises(ReadOnlyRefused):
        admit(argv)

def test_df_path_operand_requires_filesystem_scope(tmp_path):
    # Filesystem metadata for an explicit path is still an out-of-scope read.
    plan = admit(["df", "/etc"])
    assert plan.read_targets == ("/etc",)
    with pytest.raises(AuthorityViolation):
        require_targets_in_scope(plan, tmp_path, tmp_path)
    assert admit(["df", "-h"]).read_targets == ()
