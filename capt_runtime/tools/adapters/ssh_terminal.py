"""Governed ToolRequest adapter for the strict named-profile SSH backend."""
from __future__ import annotations

import json
from typing import Any

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.backends.ssh import (
    MAX_REMOTE_CAPTURE_BYTES,
    SSHPreparedTarget,
    SSHProcessBackend,
    SSHProcessRequest,
)

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
    if not all(isinstance(item, str) and item and "\x00" not in item for item in parsed):
        raise ValueError("argv elements must be non-empty strings without NUL")
    if sum(len(item.encode("utf-8")) for item in parsed) > MAX_ARG_BYTES:
        raise ValueError(f"argv exceeds {MAX_ARG_BYTES} encoded bytes")
    return tuple(parsed)


def _out(kind: str, name: str, value: Any) -> dict[str, Any]:
    return {"kind": kind, "name": name, "value": value}


class SSHTerminalToolAdapter:
    adapter_id = "adapter-terminal-ssh"
    supports_reconciliation = False

    def __init__(self, backend: SSHProcessBackend) -> None:
        self.backend = backend

    def readiness(self) -> dict[str, object]:
        return self.backend.readiness()

    def _process_request(self, request: dict[str, Any]) -> SSHProcessRequest:
        if request.get("toolId") != "terminal.ssh":
            raise AuthorityViolation("SSHTerminalToolAdapter requires toolId=terminal.ssh")
        if request.get("operation") != "terminal.exec":
            raise AuthorityViolation(
                f"unsupported SSH terminal operation: {request.get('operation')}"
            )
        if request.get("backendId") != "ssh":
            raise AuthorityViolation("SSHTerminalToolAdapter requires backendId=ssh")
        profile_id = request.get("targetIdentity")
        if not isinstance(profile_id, str) or not profile_id:
            raise AuthorityViolation("SSH ToolRequest targetIdentity must name an SSH profile")
        filesystem_scope = request.get("filesystemScope")
        if not isinstance(filesystem_scope, str) or not filesystem_scope:
            raise AuthorityViolation("SSH terminal execution requires a remote filesystemScope")
        args = _arguments(request)
        cwd = args["cwd"]
        if not isinstance(cwd, str):
            raise ValueError("cwd must be a path string")
        timeout_ms = _integer(
            args.get("timeout_ms", 30_000), "timeout_ms", minimum=1, maximum=MAX_TIMEOUT_MS
        )
        stdout_limit = _integer(
            args.get("stdout_limit_bytes", 1024 * 1024),
            "stdout_limit_bytes",
            minimum=0,
            maximum=MAX_REMOTE_CAPTURE_BYTES,
        )
        stderr_limit = _integer(
            args.get("stderr_limit_bytes", 1024 * 1024),
            "stderr_limit_bytes",
            minimum=0,
            maximum=MAX_REMOTE_CAPTURE_BYTES,
        )
        return SSHProcessRequest(
            profile_id=profile_id,
            argv=_parse_argv(args["argv"]),
            cwd=cwd,
            filesystem_root=filesystem_scope,
            timeout_seconds=timeout_ms / 1000.0,
            stdout_limit_bytes=stdout_limit,
            stderr_limit_bytes=stderr_limit,
        )

    def preflight(self, request: dict[str, Any]) -> SSHPreparedTarget:
        """Perform request-specific admission checks without executing user argv."""
        return self.backend.preflight(self._process_request(request))

    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        result = self.backend.execute(self._process_request(request))
        if result.denied:
            return {
                "status": "denied",
                "exitCode": None,
                "output": [
                    _out("string", "denial", result.denial_reason),
                    _out("string", "profileId", result.profile_id),
                    _out("string", "hostFingerprint", result.host_fingerprint),
                    _out("string", "remoteCwd", result.remote_cwd),
                ],
                "sideEffectIdentity": None,
                "error": None,
            }
        if result.timed_out:
            status = "indeterminate"
        elif result.exit_code == 0:
            status = "succeeded"
        else:
            status = "failed"
        identity = json.dumps(
            {
                "backend": "ssh",
                "profileId": result.profile_id,
                "hostFingerprint": result.host_fingerprint,
                "remoteCwd": result.remote_cwd,
                "remotePid": result.remote_pid,
                "remoteProcessGroupId": result.remote_process_group_id,
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
            _out("string", "profileId", result.profile_id),
            _out("string", "hostFingerprint", result.host_fingerprint),
            _out("string", "remoteCwd", result.remote_cwd),
            _out("integer", "remotePid", result.remote_pid),
            _out("integer", "remoteProcessGroupId", result.remote_process_group_id),
        ]
        if status == "indeterminate":
            output.append(
                _out(
                    "string",
                    "reconciliation",
                    "Remote SSH execution crossed the dispatch boundary and timed out; "
                    "durable remote effects before termination may exist.",
                )
            )
        return {
            "status": status,
            "exitCode": result.exit_code,
            "output": output,
            "sideEffectIdentity": identity,
            "error": None,
        }
