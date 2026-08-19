"""Real local Python execution adapter backed only by LocalProcessBackend.

Filesystem scope constrains the admitted working directory. It is not an OS
sandbox and this adapter deliberately makes no stronger isolation claim.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.backends.local import (
    MAX_CAPTURE_BYTES,
    LocalProcessBackend,
    LocalProcessRequest,
)
from capt_runtime.tools.scope import require_scoped_path

MAX_CODE_BYTES = 65_536
MAX_TIMEOUT_MS = 3_600_000

_ALLOWED_ARGUMENTS = {
    "code",
    "cwd",
    "timeout_ms",
    "stdout_limit_bytes",
    "stderr_limit_bytes",
}
_REQUIRED_ARGUMENTS = {"code", "cwd"}


def _arguments(request: dict[str, Any]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for item in request.get("arguments", []):
        name = item.get("name")
        if name in parsed:
            raise ValueError(f"duplicate argument: {name}")
        if name not in _ALLOWED_ARGUMENTS:
            raise ValueError(f"unknown argument for code.execute_python: {name}")
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


def _out(kind: str, name: str, value: Any) -> dict[str, Any]:
    return {"kind": kind, "name": name, "value": value}


class CodeExecutionAdapter:
    adapter_id = "adapter-code-execution"
    supports_reconciliation = False

    def __init__(self, backend: LocalProcessBackend | None = None) -> None:
        self.backend = backend or LocalProcessBackend()

    @staticmethod
    def readiness() -> dict[str, object]:
        executable = Path(sys.executable)
        available = executable.is_file() and os.access(executable, os.X_OK)
        return {
            "status": "available" if available else "unavailable",
            "reason": (
                f"Python interpreter available at {executable}"
                if available
                else f"Python interpreter unavailable at {executable}"
            ),
        }

    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        if request.get("toolId") != "code.execution":
            raise AuthorityViolation("CodeExecutionAdapter requires toolId=code.execution")
        if request.get("operation") != "code.execute_python":
            raise AuthorityViolation(
                f"unsupported code operation: {request.get('operation')}"
            )
        if request.get("backendId") != "local":
            raise AuthorityViolation("CodeExecutionAdapter supports only backendId=local")
        scope = request.get("filesystemScope")
        if not scope:
            raise AuthorityViolation("code execution requires filesystemScope")
        args = _arguments(request)
        cwd = require_scoped_path(scope, args["cwd"])
        if not cwd.is_dir():
            raise AuthorityViolation(f"code execution cwd is not a directory: {cwd}")

        code = args["code"]
        if not isinstance(code, str):
            raise ValueError("code must be a string")
        encoded = code.encode("utf-8")
        if len(encoded) > MAX_CODE_BYTES:
            raise ValueError(f"code exceeds {MAX_CODE_BYTES} bytes")

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

        fd, script_name = tempfile.mkstemp(
            prefix=".capt-python-", suffix=".py", dir=str(cwd)
        )
        script = Path(script_name)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb", closefd=True) as handle:
                fd = -1
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            script_digest = "sha256:" + hashlib.sha256(encoded).hexdigest()
            result = self.backend.execute(
                LocalProcessRequest(
                    argv=(sys.executable, str(script)),
                    cwd=cwd,
                    filesystem_root=Path(scope),
                    timeout_seconds=timeout_ms / 1000.0,
                    stdout_limit_bytes=stdout_limit,
                    stderr_limit_bytes=stderr_limit,
                )
            )
        finally:
            if fd >= 0:
                os.close(fd)
            try:
                script.unlink()
            except FileNotFoundError:
                pass

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
                "scriptDigest": script_digest,
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
            _out("string", "scriptDigest", script_digest),
        ]
        if status == "indeterminate":
            output.append(
                _out(
                    "string",
                    "reconciliation",
                    "Python execution crossed the dispatch boundary but was interrupted; "
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
