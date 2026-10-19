"""UPG-071: governed terminal.inspect (not a terminal.exec effect downgrade).

This adapter cannot confer CAPT capability authority; ToolBroker binds the
terminal.inspect grant and the declared pure_read_only operation independently.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.adapters.terminal import (
    _arguments,
    _integer,
    _out,
    _parse_argv,
)
from capt_runtime.tools.backends.local import (
    LocalProcessBackend,
    LocalProcessRequest,
)
from capt_runtime.tools.readonly_argv import (
    GIT_PROBE_ARGV,
    ReadOnlyRefused,
    admit,
    finalize_git_argv,
    git_filter_driver_names,
    require_targets_in_scope,
)
from capt_runtime.tools.scope import require_scoped_path

_SAFE_BIN_DIRS = ("/bin", "/usr/bin", "/sbin", "/usr/sbin")
_SAFE_PATH = ":".join(_SAFE_BIN_DIRS)
_MAX_CAPTURE = 512 * 1024
_MAX_TIMEOUT_MS = 30000


def _system_executable(name: str) -> str:
    """Do not execute a caller-installed same-name executable from PATH."""
    if "/" in name or name in {".", ".."}:
        raise ReadOnlyRefused("READONLY_REFUSED:untrusted-executable")
    for directory in _SAFE_BIN_DIRS:
        candidate = Path(directory) / name
        try:
            if candidate.is_file() and os.access(candidate, os.X_OK):
                canonical = candidate.resolve(strict=True)
                if any(canonical.is_relative_to(Path(root)) for root in _SAFE_BIN_DIRS):
                    return str(candidate)
        except OSError:
            pass
    raise ReadOnlyRefused("READONLY_REFUSED:system-executable-unavailable:" + name)


class TerminalInspectToolAdapter:
    adapter_id = "adapter-terminal-inspect"
    supports_reconciliation = False

    def __init__(self, backend: LocalProcessBackend | None = None):
        self.backend = backend or LocalProcessBackend()

    def readiness(self) -> dict[str, object]:
        return self.backend.readiness()

    def _execute_plan(
        self,
        argv: tuple[str, ...],
        cwd: Path,
        scope: Path,
        overrides: tuple[tuple[str, str], ...],
        timeout_ms: int,
        capture: int,
    ):
        # A trusted, OS-shipped binary, no shell and no untrusted PATH lookup.
        safe_argv = (_system_executable(argv[0]), *argv[1:])
        env = dict(overrides)
        env["PATH"] = _SAFE_PATH
        return self.backend.execute(LocalProcessRequest(
            argv=safe_argv,
            cwd=cwd,
            filesystem_root=scope,
            timeout_seconds=timeout_ms / 1000,
            stdout_limit_bytes=capture,
            stderr_limit_bytes=capture,
            env_overrides=env,
        ))

    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        if request.get("toolId") != "terminal.inspect" or request.get("operation") != "terminal.inspect":
            raise AuthorityViolation("terminal.inspect requires its exact tool and operation")
        if request.get("backendId") != "local":
            raise AuthorityViolation("terminal.inspect requires backendId=local")
        scope_value = request.get("filesystemScope")
        if not isinstance(scope_value, str) or not scope_value:
            raise AuthorityViolation("terminal.inspect requires explicit filesystemScope")
        scope = Path(scope_value).resolve(strict=True)
        args = _arguments(request)
        argv = _parse_argv(args["argv"])
        # Git transitively reads config/includes and Git directories outside
        # the allowed root. Until OS-isolated Git exists, fail closed.
        if argv[0] in {"git", "jq"}:
            # jq can import arbitrary external files through filter syntax;
            # bounding only named argv operands is not sufficient.
            raise ReadOnlyRefused("READONLY_REFUSED:unbounded-ambient-file-read")
        cwd = require_scoped_path(scope, args["cwd"])
        if not cwd.is_dir():
            raise AuthorityViolation("terminal.inspect cwd must exist")
        timeout_ms = _integer(args.get("timeout_ms", 10000), "timeout_ms", minimum=1, maximum=_MAX_TIMEOUT_MS)
        capture = _integer(args.get("stdout_limit_bytes", 65536), "stdout_limit_bytes", minimum=0, maximum=_MAX_CAPTURE)
        stderr_limit = _integer(args.get("stderr_limit_bytes", 65536), "stderr_limit_bytes", minimum=0, maximum=_MAX_CAPTURE)
        # A single output limit keeps all captured output bounded.
        capture = min(capture, stderr_limit)
        plan = admit(argv)  # deny-list and grammar, not CAPT authorization
        require_targets_in_scope(plan, scope, cwd)
        candidate_argv = plan.argv
        if plan.needs_filter_probe:
            probe = self._execute_plan(
                GIT_PROBE_ARGV, cwd, scope, plan.env_overrides, min(timeout_ms, 5000), 65536
            )
            if probe.timed_out or probe.cancelled or probe.exit_code not in (0, 1):
                raise ReadOnlyRefused("READONLY_REFUSED:git-filter-probe-failed")
            if probe.stderr:
                raise ReadOnlyRefused("READONLY_REFUSED:git-filter-probe-stderr")
            drivers = git_filter_driver_names(probe.stdout.encode("utf-8"))
            candidate_argv = finalize_git_argv(plan, drivers)
        result = self._execute_plan(candidate_argv, cwd, scope, plan.env_overrides, timeout_ms, capture)
        # Interruption is never presented as a successfully completed read.
        status = ("indeterminate" if result.timed_out or result.cancelled
                  else "succeeded" if result.exit_code == 0 else "failed")
        return {
            "status": status,
            "exitCode": result.exit_code,
            "output": [
                _out("string", "stdout", result.stdout),
                _out("string", "stderr", result.stderr),
                _out("boolean", "timedOut", result.timed_out),
                _out("boolean", "cancelled", result.cancelled),
                _out("string", "admissionPolicy", plan.policy_version),
            ],
            "sideEffectIdentity": None,
            "error": None,
        }
