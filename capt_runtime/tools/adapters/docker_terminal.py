"""Governed ToolRequest adapter for local named-profile Docker execution."""
from __future__ import annotations

import json
import threading
from copy import deepcopy
from typing import Any

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.backends.docker import (
    MAX_DOCKER_CAPTURE_BYTES,
    DockerPreparedTarget,
    DockerProcessBackend,
    DockerProcessRequest,
)

MAX_TIMEOUT_MS = 3_600_000
MAX_ARGV_ITEMS = 1024
MAX_ARG_BYTES = 65_536
_ALLOWED_ARGUMENTS = {"argv", "cwd", "timeout_ms", "stdout_limit_bytes", "stderr_limit_bytes"}
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


class DockerTerminalToolAdapter:
    adapter_id = "adapter-terminal-docker"
    supports_reconciliation = False

    def __init__(self, backend: DockerProcessBackend) -> None:
        self.backend = backend
        self._prepared: dict[str, DockerPreparedTarget] = {}
        self._prepared_lock = threading.Lock()

    def readiness(self) -> dict[str, object]:
        return self.backend.readiness()

    @staticmethod
    def _key(request: dict[str, Any]) -> str:
        return f"{request.get('toolRequestId')}:{request.get('operationFingerprint')}"

    def _process_request(self, request: dict[str, Any]) -> DockerProcessRequest:
        if request.get("toolId") != "terminal.docker":
            raise AuthorityViolation("DockerTerminalToolAdapter requires toolId=terminal.docker")
        if request.get("operation") != "terminal.exec":
            raise AuthorityViolation(
                f"unsupported Docker terminal operation: {request.get('operation')}"
            )
        if request.get("backendId") != "docker":
            raise AuthorityViolation("DockerTerminalToolAdapter requires backendId=docker")
        profile_id = request.get("targetIdentity")
        if not isinstance(profile_id, str) or not profile_id:
            raise AuthorityViolation("Docker targetIdentity must name a Docker profile")
        filesystem_scope = request.get("filesystemScope")
        if not isinstance(filesystem_scope, str) or not filesystem_scope:
            raise AuthorityViolation("Docker execution requires a container filesystemScope")
        args = _arguments(request)
        cwd = args["cwd"]
        if not isinstance(cwd, str):
            raise ValueError("cwd must be a path string")
        return DockerProcessRequest(
            profile_id=profile_id,
            argv=_parse_argv(args["argv"]),
            cwd=cwd,
            filesystem_root=filesystem_scope,
            timeout_seconds=_integer(
                args.get("timeout_ms", 30_000), "timeout_ms", minimum=1, maximum=MAX_TIMEOUT_MS
            ) / 1000.0,
            stdout_limit_bytes=_integer(
                args.get("stdout_limit_bytes", 1024 * 1024),
                "stdout_limit_bytes",
                minimum=0,
                maximum=MAX_DOCKER_CAPTURE_BYTES,
            ),
            stderr_limit_bytes=_integer(
                args.get("stderr_limit_bytes", 1024 * 1024),
                "stderr_limit_bytes",
                minimum=0,
                maximum=MAX_DOCKER_CAPTURE_BYTES,
            ),
        )

    def preflight(self, request: dict[str, Any]) -> DockerPreparedTarget:
        prepared = self.backend.preflight(self._process_request(request))
        key = self._key(request)
        with self._prepared_lock:
            if len(self._prepared) >= 256:
                self._prepared.pop(next(iter(self._prepared)))
            self._prepared[key] = prepared
        return prepared

    def execute_observed(self, request: dict[str, Any], observe_effect) -> dict[str, Any]:
        process_request = self._process_request(request)
        key = self._key(request)
        with self._prepared_lock:
            prepared = self._prepared.pop(key, None)
        prepared = prepared or self.backend.preflight(process_request)
        result = self.backend.execute(
            process_request,
            prepared=prepared,
            observe_effect=observe_effect,
        )
        identity = None
        if result.container_id:
            identity = self.backend.effect_identity(
                prepared, result.container_id, result.container_cwd
            )
        if not result.cleanup_succeeded or result.control_error:
            status = "indeterminate"
        elif result.timed_out:
            status = "indeterminate"
        elif result.exit_code == 0:
            status = "succeeded"
        else:
            status = "failed"
        output = [
            _out("string", "stdout", result.stdout),
            _out("string", "stderr", result.stderr),
            _out("integer", "stdoutTotalBytes", result.stdout_total_bytes),
            _out("integer", "stderrTotalBytes", result.stderr_total_bytes),
            _out("boolean", "stdoutTruncated", result.stdout_truncated),
            _out("boolean", "stderrTruncated", result.stderr_truncated),
            _out("boolean", "timedOut", result.timed_out),
            _out("string", "profileId", result.profile_id),
            _out("string", "imageId", result.image_id),
            _out("string", "containerCwd", result.container_cwd),
            _out("boolean", "cleanupSucceeded", result.cleanup_succeeded),
        ]
        if result.repo_digest is not None:
            output.append(_out("string", "repoDigest", result.repo_digest))
        if result.container_id:
            output.append(_out("string", "containerId", result.container_id))
        if result.cleanup_error:
            output.append(_out("string", "cleanupError", result.cleanup_error))
        if result.control_error:
            output.append(_out("string", "controlError", result.control_error))
        if status == "indeterminate":
            output.append(
                _out(
                    "string",
                    "reconciliation",
                    "Docker execution crossed the dispatch boundary; timeout/control/cleanup state "
                    "prevents proving the complete durable-local effect set.",
                )
            )
        return {
            "status": status,
            "exitCode": result.exit_code,
            "output": output,
            "sideEffectIdentity": identity,
            "error": None,
        }
