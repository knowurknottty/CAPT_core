"""Governed ToolRequest adapter for CAPT InversionSandbox execution."""
from __future__ import annotations

import threading
from typing import Any

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.adapters.docker_terminal import (
    MAX_TIMEOUT_MS,
    _arguments,
    _integer,
    _out,
    _parse_argv,
)
from capt_runtime.tools.backends.docker import (
    MAX_DOCKER_CAPTURE_BYTES,
    DockerProcessRequest,
)
from capt_runtime.tools.backends.inversion_sandbox import (
    InversionSandboxPreparedTarget,
    InversionSandboxProcessBackend,
)


class InversionSandboxTerminalToolAdapter:
    adapter_id = "adapter-terminal-inversion-sandbox"
    supports_reconciliation = False

    def __init__(self, backend: InversionSandboxProcessBackend) -> None:
        self.backend = backend
        self._prepared: dict[str, InversionSandboxPreparedTarget] = {}
        self._prepared_lock = threading.Lock()

    def readiness(self) -> dict[str, object]:
        return self.backend.readiness()

    @staticmethod
    def _key(request: dict[str, Any]) -> str:
        return f"{request.get('toolRequestId')}:{request.get('operationFingerprint')}"

    def _process_request(self, request: dict[str, Any]) -> DockerProcessRequest:
        if request.get("toolId") != "terminal.inversion_sandbox":
            raise AuthorityViolation(
                "InversionSandboxTerminalToolAdapter requires toolId=terminal.inversion_sandbox"
            )
        if request.get("operation") != "terminal.exec":
            raise AuthorityViolation(
                f"unsupported InversionSandbox operation: {request.get('operation')}"
            )
        if request.get("backendId") != "inversion_sandbox":
            raise AuthorityViolation(
                "InversionSandboxTerminalToolAdapter requires backendId=inversion_sandbox"
            )
        profile_id = request.get("targetIdentity")
        if not isinstance(profile_id, str) or not profile_id:
            raise AuthorityViolation("InversionSandbox targetIdentity must name a profile")
        filesystem_scope = request.get("filesystemScope")
        if not isinstance(filesystem_scope, str) or not filesystem_scope:
            raise AuthorityViolation("InversionSandbox requires a container filesystemScope")
        args = _arguments(request)
        cwd = args["cwd"]
        if not isinstance(cwd, str):
            raise TypeError("cwd must be a path string")
        return DockerProcessRequest(
            profile_id=profile_id,
            argv=_parse_argv(args["argv"]),
            cwd=cwd,
            filesystem_root=filesystem_scope,
            timeout_seconds=_integer(
                args.get("timeout_ms", 30_000),
                "timeout_ms",
                minimum=1,
                maximum=MAX_TIMEOUT_MS,
            ) / 1000.0,
            stdout_limit_bytes=_integer(
                args.get("stdout_limit_bytes", 1024 * 1024),
                "stdout_limit_bytes", minimum=0, maximum=MAX_DOCKER_CAPTURE_BYTES,
            ),
            stderr_limit_bytes=_integer(
                args.get("stderr_limit_bytes", 1024 * 1024),
                "stderr_limit_bytes", minimum=0, maximum=MAX_DOCKER_CAPTURE_BYTES,
            ),
        )

    def preflight(self, request: dict[str, Any]) -> InversionSandboxPreparedTarget:
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
        docker = result.docker
        if not docker.cleanup_succeeded or docker.control_error or docker.timed_out:
            status = "indeterminate"
        elif docker.exit_code == 0:
            status = "succeeded"
        else:
            status = "failed"
        output = [
            _out("string", "stdout", docker.stdout),
            _out("string", "stderr", docker.stderr),
            _out("integer", "stdoutTotalBytes", docker.stdout_total_bytes),
            _out("integer", "stderrTotalBytes", docker.stderr_total_bytes),
            _out("boolean", "stdoutTruncated", docker.stdout_truncated),
            _out("boolean", "stderrTruncated", docker.stderr_truncated),
            _out("boolean", "timedOut", docker.timed_out),
            _out("string", "profileId", docker.profile_id),
            _out("string", "imageId", docker.image_id),
            _out("string", "containerCwd", docker.container_cwd),
            _out("boolean", "cleanupSucceeded", docker.cleanup_succeeded),
        ]
        if docker.repo_digest is not None:
            output.append(_out("string", "repoDigest", docker.repo_digest))
        if docker.container_id:
            output.append(_out("string", "containerId", docker.container_id))
        if result.attestation is not None:
            output.extend(
                [
                    _out("string", "securityProfileDigest", result.attestation.security_profile_digest),
                    _out("string", "networkPolicyDigest", result.attestation.network_policy_digest),
                    _out("string", "filesystemScopeDigest", result.attestation.filesystem_scope_digest),
                    _out("string", "attestationDigest", result.attestation.digest),
                ]
            )
        if docker.cleanup_error:
            output.append(_out("string", "cleanupError", docker.cleanup_error))
        if docker.control_error:
            output.append(_out("string", "controlError", docker.control_error))
        if status == "indeterminate":
            output.append(
                _out(
                    "string",
                    "reconciliation",
                    "InversionSandbox crossed dispatch; control/cleanup state prevents proving the complete effect set.",
                )
            )
        return {
            "status": status,
            "exitCode": docker.exit_code,
            "output": output,
            "sideEffectIdentity": result.side_effect_identity,
            "error": None,
        }
