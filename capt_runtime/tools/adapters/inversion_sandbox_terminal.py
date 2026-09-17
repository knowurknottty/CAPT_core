"""Governed ToolRequest adapter for CAPT InversionSandbox execution."""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Callable

from capt_runtime.contracts import digest, require
from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.adapters.docker_terminal import (
    MAX_TIMEOUT_MS,
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
    SandboxRuntimeIdentity,
)
from capt_runtime.tools.sandbox_broker_hooks import SandboxTerminalPatch

_ALLOWED_ARGUMENTS = {
    "argv", "cwd", "timeout_ms", "stdout_limit_bytes", "stderr_limit_bytes",
    "sandbox_lease_id",
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
    sandbox_lease_id = parsed.get("sandbox_lease_id")
    if sandbox_lease_id is not None and (
        not isinstance(sandbox_lease_id, str) or not sandbox_lease_id
    ):
        raise ValueError("sandbox_lease_id must be a non-empty string")
    return parsed


def _now_rfc3339() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class InversionSandboxTerminalToolAdapter:
    adapter_id = "adapter-terminal-inversion-sandbox"
    supports_reconciliation = False

    def __init__(
        self,
        backend: InversionSandboxProcessBackend,
        *,
        lease_resolver: Callable[[str], dict[str, Any] | None] | None = None,
        now: Callable[[], str] | None = None,
    ) -> None:
        self.backend = backend
        self._lease_resolver = lease_resolver
        self._now = now or _now_rfc3339
        self._prepared: dict[str, InversionSandboxPreparedTarget] = {}
        self._persistent_identity: dict[str, SandboxRuntimeIdentity] = {}
        self._prepared_lock = threading.Lock()

    def readiness(self) -> dict[str, object]:
        return self.backend.readiness()

    @staticmethod
    def _key(request: dict[str, Any]) -> str:
        return f"{request.get('toolRequestId')}:{request.get('operationFingerprint')}"

    def _parsed(self, request: dict[str, Any]) -> tuple[DockerProcessRequest, str | None]:
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
        process = DockerProcessRequest(
            profile_id=profile_id,
            argv=_parse_argv(args["argv"]),
            cwd=cwd,
            filesystem_root=filesystem_scope,
            timeout_seconds=_integer(
                args.get("timeout_ms", 30_000), "timeout_ms", minimum=1, maximum=MAX_TIMEOUT_MS
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
        return process, args.get("sandbox_lease_id")

    def _process_request(self, request: dict[str, Any]) -> DockerProcessRequest:
        """R1-compatible one-shot parser surface."""
        return self._parsed(request)[0]

    def _require_lease(self, sandbox_lease_id: str) -> dict[str, Any]:
        if self._lease_resolver is None:
            raise AuthorityViolation("PERSISTENT_SANDBOX_LEASE_RESOLVER_UNAVAILABLE")
        state = self._lease_resolver(sandbox_lease_id)
        if state is None:
            raise AuthorityViolation("SANDBOX_LEASE_NOT_FOUND")
        require("SandboxLease", state)
        return state

    def _validate_resource_state(
        self, request: dict[str, Any], state: dict[str, Any]
    ) -> None:
        if state["profileId"] != request["targetIdentity"]:
            raise AuthorityViolation("SANDBOX_PROFILE_IDENTITY_MISMATCH")
        if state["state"] != "running":
            raise AuthorityViolation("SANDBOX_LEASE_NOT_RUNNING")
        if self._now() >= state["expiresAt"]:
            raise AuthorityViolation("SANDBOX_LEASE_EXPIRED")

    @staticmethod
    def _identity_from_state(state: dict[str, Any]) -> SandboxRuntimeIdentity:
        required = ("containerId", "creationAttestationDigest", "sideEffectIdentity")
        if any(not state.get(name) for name in required):
            raise AuthorityViolation("SANDBOX_LEASE_RUNTIME_IDENTITY_INCOMPLETE")
        return SandboxRuntimeIdentity(
            sandbox_lease_id=state["sandboxLeaseId"],
            profile_id=state["profileId"],
            profile_digest=state["profileDigest"],
            context_endpoint=state["dockerEndpoint"],
            daemon_identity_digest=state["daemonIdentityDigest"],
            workload_container_id=state["containerId"],
            workload_image_id=state["imageId"],
            security_profile_digest=state["securityProfileDigest"],
            network_policy_digest=state["networkPolicyDigest"],
            filesystem_scope_digest=state["filesystemScopeDigest"],
            persistent_entrypoint_digest=state["persistentEntrypointDigest"],
            creation_attestation_digest=state["creationAttestationDigest"],
            guardian_container_id=state.get("guardianContainerId"),
            guardian_image_id=state.get("guardianImageId"),
            internal_network_name=state.get("networkName"),
            internal_network_id=state.get("networkId"),
        )

    def validate_persistent_exec_context(
        self, request: dict[str, Any], *, operator_id: str, session_id: str
    ) -> None:
        _process, sandbox_lease_id = self._parsed(request)
        if sandbox_lease_id is None:
            return
        state = self._require_lease(sandbox_lease_id)
        self._validate_resource_state(request, state)
        if state["operatorId"] != operator_id or state["sessionId"] != session_id:
            raise AuthorityViolation("SANDBOX_OWNER_IDENTITY_MISMATCH")

    def preflight(self, request: dict[str, Any]) -> object:
        process_request, sandbox_lease_id = self._parsed(request)
        key = self._key(request)
        if sandbox_lease_id is None:
            prepared = self.backend.preflight(process_request)
            with self._prepared_lock:
                if len(self._prepared) >= 256:
                    self._prepared.pop(next(iter(self._prepared)))
                self._prepared[key] = prepared
            return prepared
        state = self._require_lease(sandbox_lease_id)
        self._validate_resource_state(request, state)
        identity = self._identity_from_state(state)
        observation = self.backend.inspect_persistent(identity)
        if observation.get("workloadRunning") is not True:
            raise AuthorityViolation("SANDBOX_PERSISTENT_WORKLOAD_NOT_RUNNING")
        with self._prepared_lock:
            if len(self._persistent_identity) >= 256:
                self._persistent_identity.pop(next(iter(self._persistent_identity)))
            self._persistent_identity[key] = identity
        return observation

    @staticmethod
    def _persistent_effect_identity(
        request: dict[str, Any], process_request: DockerProcessRequest,
        identity: SandboxRuntimeIdentity, observation_digest: str,
    ) -> str:
        return digest(
            {
                "sandboxLeaseId": identity.sandbox_lease_id,
                "containerId": identity.workload_container_id,
                "creationAttestationDigest": identity.creation_attestation_digest,
                "operationFingerprint": request["operationFingerprint"],
                "commandDigest": digest(
                    {
                        "argv": list(process_request.argv),
                        "cwd": process_request.cwd,
                        "filesystemRoot": process_request.filesystem_root,
                    }
                ),
                "resourceObservationDigest": observation_digest,
            }
        )

    def persistent_exec_terminal_patch(
        self, request: dict[str, Any], result: dict[str, Any], *, now: str
    ) -> SandboxTerminalPatch | None:
        _process, sandbox_lease_id = self._parsed(request)
        if (
            sandbox_lease_id is None
            or result.get("status") != "indeterminate"
            or not result.get("sideEffectIdentity")
        ):
            return None
        timeout_unknown = any(
            item.get("name") == "reconciliation" and item.get("value") == "exec_termination_unknown"
            for item in result.get("output", [])
        )
        reason = "exec_termination_unknown" if timeout_unknown else "persistent_exec_indeterminate"
        return SandboxTerminalPatch(
            sandbox_lease_id,
            {"reconciliationReason": reason, "updatedAt": now},
        )

    def execute_observed(self, request: dict[str, Any], observe_effect) -> dict[str, Any]:
        process_request, sandbox_lease_id = self._parsed(request)
        key = self._key(request)
        if sandbox_lease_id is None:
            with self._prepared_lock:
                prepared = self._prepared.pop(key, None)
            prepared = prepared or self.backend.preflight(process_request)
            return self._one_shot(process_request, prepared, observe_effect)

        with self._prepared_lock:
            identity = self._persistent_identity.pop(key, None)
        if identity is None:
            state = self._require_lease(sandbox_lease_id)
            self._validate_resource_state(request, state)
            identity = self._identity_from_state(state)

        observed: dict[str, str] = {}

        def observe_resource(observation_digest: str) -> None:
            effect_identity = self._persistent_effect_identity(
                request, process_request, identity, observation_digest
            )
            observe_effect(effect_identity)
            observed["identity"] = effect_identity

        result = self.backend.exec_persistent(
            identity,
            argv=process_request.argv,
            cwd=process_request.cwd,
            filesystem_root=process_request.filesystem_root,
            timeout_seconds=process_request.timeout_seconds,
            stdout_limit_bytes=process_request.stdout_limit_bytes,
            stderr_limit_bytes=process_request.stderr_limit_bytes,
            observe_effect=observe_resource,
        )
        effect_identity = observed.get("identity")
        if effect_identity is None:
            raise RuntimeError("persistent sandbox exec returned without effect observation")
        if not result.termination_proven:
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
            _out("boolean", "terminationProven", result.termination_proven),
            _out("string", "profileId", identity.profile_id),
            _out("string", "imageId", identity.workload_image_id),
            _out("string", "containerCwd", process_request.cwd),
            _out("string", "containerId", identity.workload_container_id),
            _out("string", "sandboxLeaseId", identity.sandbox_lease_id),
            _out("string", "resourceObservationDigest", result.observation_digest),
        ]
        if status == "indeterminate":
            output.append(_out("string", "reconciliation", "exec_termination_unknown"))
        return {
            "status": status,
            "exitCode": result.exit_code,
            "output": output,
            "sideEffectIdentity": effect_identity,
            "error": None,
        }

    def _one_shot(
        self,
        process_request: DockerProcessRequest,
        prepared: InversionSandboxPreparedTarget,
        observe_effect,
    ) -> dict[str, Any]:
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
