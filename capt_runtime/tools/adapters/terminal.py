"""ToolRequest adapter for CAPT's bounded local process backend.

The operation contract is explicit argv only. The `argv` ToolArgument is a
canonical JSON array of strings because the current closed ToolArgument union
contains scalar values only. No shell command form is accepted.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.backends.local import (
    MAX_CAPTURE_BYTES,
    LocalProcessBackend,
    LocalProcessRequest,
)
from capt_runtime.tools.scope import require_scoped_path

MAX_TIMEOUT_MS = 3_600_000
MAX_ARGV_ITEMS = 1024
MAX_ARG_BYTES = 65_536

_ALLOWED_ARGUMENTS = {
    "argv",
    "cwd",
    "timeout_ms",
    "stdout_limit_bytes",
    "stderr_limit_bytes",
}
_REQUIRED_ARGUMENTS = {"argv", "cwd"}


def _arguments(request: dict[str, Any]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for item in request.get("arguments", []):
        name = item.get("name")
        if name in parsed:
            raise ValueError(f"duplicate argument: {name}")
        if name not in _ALLOWED_ARGUMENTS:
            raise ValueError(f"unknown argument for terminal.exec: {name}")
        parsed[name] = item.get("value")
    missing = _REQUIRED_ARGUMENTS.difference(parsed)
    if missing:
        raise ValueError(f"missing required argument(s): {', '.join(sorted(missing))}")
    return parsed


def _integer(value: Any, name: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be in [{minimum}, {maximum}]")
    return value


def _parse_argv(value: Any) -> tuple[str, ...]:
    if not isinstance(value, str):
        raise ValueError("argv must be a JSON string")
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("argv must contain valid JSON") from exc
    if not isinstance(parsed, list):
        raise ValueError("argv must be a JSON array")
    if not parsed:
        raise ValueError("argv must not be empty")
    if len(parsed) > MAX_ARGV_ITEMS:
        raise ValueError(f"argv exceeds {MAX_ARGV_ITEMS} elements")
    if not all(isinstance(item, str) for item in parsed):
        raise ValueError("argv elements must be strings")
    if any(not item or "\x00" in item for item in parsed):
        raise ValueError("argv elements must be non-empty strings without NUL")
    if sum(len(item.encode("utf-8")) for item in parsed) > MAX_ARG_BYTES:
        raise ValueError(f"argv exceeds {MAX_ARG_BYTES} encoded bytes")
    return tuple(parsed)


def _out(kind: str, name: str, value: Any) -> dict[str, Any]:
    return {"kind": kind, "name": name, "value": value}


class TerminalToolAdapter:
    adapter_id = "adapter-terminal-local"
    supports_reconciliation = False

    def __init__(self, backend: LocalProcessBackend | None = None) -> None:
        self.backend = backend or LocalProcessBackend()

    def readiness(self) -> dict[str, object]:
        return self.backend.readiness()

    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        if request.get("toolId") != "terminal.local":
            raise AuthorityViolation("TerminalToolAdapter requires toolId=terminal.local")
        if request.get("operation") != "terminal.exec":
            raise AuthorityViolation(
                f"unsupported terminal operation: {request.get('operation')}"
            )
        if request.get("backendId") != "local":
            raise AuthorityViolation("TerminalToolAdapter supports only backendId=local")
        scope = request.get("filesystemScope")
        if not scope:
            raise AuthorityViolation("terminal execution requires filesystemScope")

        args = _arguments(request)
        argv = _parse_argv(args["argv"])
        cwd = require_scoped_path(scope, args["cwd"])
        if not cwd.is_dir():
            raise AuthorityViolation(f"terminal cwd is not a directory: {cwd}")
        timeout_ms = _integer(
            args.get("timeout_ms", 30_000),
            "timeout_ms",
            minimum=1,
            maximum=MAX_TIMEOUT_MS,
        )
        stdout_limit = _integer(
            args.get("stdout_limit_bytes", 1024 * 1024),
            "stdout_limit_bytes",
            minimum=0,
            maximum=MAX_CAPTURE_BYTES,
        )
        stderr_limit = _integer(
            args.get("stderr_limit_bytes", 1024 * 1024),
            "stderr_limit_bytes",
            minimum=0,
            maximum=MAX_CAPTURE_BYTES,
        )
        result = self.backend.execute(
            LocalProcessRequest(
                argv=argv,
                cwd=cwd,
                filesystem_root=Path(scope),
                timeout_seconds=timeout_ms / 1000.0,
                stdout_limit_bytes=stdout_limit,
                stderr_limit_bytes=stderr_limit,
            )
        )
        if result.timed_out or result.cancelled:
            status = "indeterminate"
        elif result.exit_code == 0:
            status = "succeeded"
        else:
            status = "failed"
        identity = json.dumps(
            {
                "backend": "local",
                "pid": result.pid,
                "processGroupId": result.process_group_id,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        output = [
            _out("string", "stdout", result.stdout),
            _out("string", "stderr", result.stderr),
            _out("integer", "stdoutTotalBytes", result.stdout_total_bytes),
            _out("integer", "stderrTotalBytes", result.stderr_total_bytes),
            _out("boolean", "stdoutTruncated", result.stdout_truncated),
            _out("boolean", "stderrTruncated", result.stderr_truncated),
            _out("boolean", "timedOut", result.timed_out),
            _out("boolean", "cancelled", result.cancelled),
            _out("integer", "pid", result.pid),
            _out("integer", "processGroupId", result.process_group_id),
        ]
        if status == "indeterminate":
            output.append(
                _out(
                    "string",
                    "reconciliation",
                    "Terminal execution crossed the dispatch boundary but was interrupted; "
                    "arbitrary durable local effects cannot be proven absent.",
                )
            )
        return {
            "status": status,
            "exitCode": result.exit_code,
            "output": output,
            "sideEffectIdentity": identity,
            "error": None,
        }
