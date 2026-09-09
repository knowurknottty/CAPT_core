"""Governed lifecycle adapter for persistent CAPT InversionSandbox resources."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from capt_runtime.aggregates import SandboxLeaseAggregate
from capt_runtime.contracts import digest, require
from capt_runtime.errors import AuthorityViolation, CapabilityDenied
from capt_runtime.store import EventStore
from capt_runtime.tools.adapters.docker_terminal import _integer, _out
from capt_runtime.tools.backends.docker import DockerProcessRequest
from capt_runtime.tools.backends.inversion_sandbox import (
    InversionSandboxPreparedTarget,
    InversionSandboxProcessBackend,
    SandboxRuntimeIdentity,
)
from capt_runtime.tools.sandbox_broker_hooks import (
    CapabilityLeaseBoundary,
    SandboxCloseBegin,
    SandboxLeaseReservation,
    SandboxTerminalPatch,
)

_ALLOWED = {
    "sandbox.create": {"sandbox_lease_id", "ttl_seconds"},
    "sandbox.inspect": {"sandbox_lease_id"},
    "sandbox.close": {"sandbox_lease_id"},
}
_REQUIRED = {"sandbox_lease_id"}


def _parse_timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("sandbox lifecycle timestamp must be RFC3339 UTC")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    if parsed.tzinfo is None:
        raise ValueError("sandbox lifecycle timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _args(request: dict[str, Any]) -> dict[str, Any]:
    operation = request.get("operation")
    allowed = _ALLOWED.get(operation)
    if allowed is None:
        raise AuthorityViolation(f"unsupported InversionSandbox lifecycle operation: {operation}")
    parsed: dict[str, Any] = {}
    for item in request.get("arguments", []):
        name = item.get("name")
        if name in parsed:
            raise ValueError(f"duplicate sandbox lifecycle argument: {name}")
        if name not in allowed:
            raise ValueError(f"unknown argument for {operation}: {name}")
        parsed[name] = item.get("value")
    missing = _REQUIRED.difference(parsed)
    if missing:
        raise ValueError(f"missing required argument(s): {', '.join(sorted(missing))}")
    sandbox_lease_id = parsed["sandbox_lease_id"]
    if not isinstance(sandbox_lease_id, str) or not sandbox_lease_id:
        raise ValueError("sandbox_lease_id must be a non-empty string")
    return parsed


class InversionSandboxLifecycleToolAdapter:
    adapter_id = "adapter-sandbox-inversion-lifecycle"
    supports_reconciliation = False

    def __init__(self, backend: InversionSandboxProcessBackend, store: EventStore) -> None:
        self.backend = backend
        self.store = store
        self._prepared: dict[str, InversionSandboxPreparedTarget] = {}
        self._identities: dict[str, SandboxRuntimeIdentity] = {}
        self._close_receipts: dict[str, str] = {}
        self._already_closed: set[str] = set()
        self._lock = threading.Lock()

    @staticmethod
    def _key(request: dict[str, Any]) -> str:
        return f"{request.get('toolRequestId')}:{request.get('operationFingerprint')}"

    def readiness(self) -> dict[str, object]:
        return self.backend.readiness()

    def _validate_request(self, request: dict[str, Any]) -> dict[str, Any]:
        if request.get("toolId") != "sandbox.inversion":
            raise AuthorityViolation("sandbox lifecycle adapter requires toolId=sandbox.inversion")
        if request.get("backendId") != "inversion_sandbox":
            raise AuthorityViolation("sandbox lifecycle adapter requires backendId=inversion_sandbox")
        profile_id = request.get("targetIdentity")
        if not isinstance(profile_id, str) or not profile_id:
            raise AuthorityViolation("sandbox lifecycle targetIdentity must name a profile")
        filesystem_scope = request.get("filesystemScope")
        if not isinstance(filesystem_scope, str) or not filesystem_scope:
            raise AuthorityViolation("sandbox lifecycle requires filesystemScope")
        return _args(request)

    def _state(self, sandbox_lease_id: str) -> dict[str, Any]:
        state = self.store.load_state(SandboxLeaseAggregate.stream_id(sandbox_lease_id))
        if state is None:
            raise AuthorityViolation("SANDBOX_LEASE_NOT_FOUND")
        require("SandboxLease", state)
        return state

    def _identity_from_state(self, state: dict[str, Any]) -> SandboxRuntimeIdentity:
        required = (
            "containerId", "creationAttestationDigest", "sideEffectIdentity",
        )
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

    def _create_process_request(self, request: dict[str, Any]) -> DockerProcessRequest:
        profile = self.backend.profiles.require(str(request["targetIdentity"]))
        if profile.persistent_entrypoint_argv is None:
            raise AuthorityViolation("InversionSandbox profile is not persistent-capable")
        return DockerProcessRequest(
            profile_id=profile.profile_id,
            argv=profile.persistent_entrypoint_argv,
            cwd=profile.working_dir,
            filesystem_root=str(request["filesystemScope"]),
            timeout_seconds=30.0,
            stdout_limit_bytes=64 * 1024,
            stderr_limit_bytes=64 * 1024,
        )

    def validate_sandbox_context(
        self, request: dict[str, Any], *, operator_id: str, session_id: str
    ) -> None:
        args = self._validate_request(request)
        if request["operation"] == "sandbox.create":
            return
        state = self._state(args["sandbox_lease_id"])
        if state["profileId"] != request["targetIdentity"]:
            raise AuthorityViolation("SANDBOX_PROFILE_IDENTITY_MISMATCH")
        if state["operatorId"] != operator_id or state["sessionId"] != session_id:
            raise AuthorityViolation("SANDBOX_OWNER_IDENTITY_MISMATCH")

    def preflight(self, request: dict[str, Any]) -> object:
        args = self._validate_request(request)
        key = self._key(request)
        operation = request["operation"]
        if operation == "sandbox.create":
            prepared = self.backend.preflight(self._create_process_request(request))
            if prepared.profile.persistent_entrypoint_argv is None:
                raise AuthorityViolation("InversionSandbox profile is not persistent-capable")
            with self._lock:
                self._prepared[key] = prepared
            return prepared
        state = self._state(args["sandbox_lease_id"])
        if operation == "sandbox.close" and state["state"] == "closed":
            with self._lock:
                self._already_closed.add(key)
            return state
        if state["state"] not in {"created", "running", "indeterminate", "closing"}:
            raise AuthorityViolation(f"sandbox lifecycle operation cannot target state {state['state']}")
        identity = self._identity_from_state(state)
        if state["state"] in {"created", "running", "closing"}:
            self.backend.inspect_persistent(identity)
        with self._lock:
            self._identities[key] = identity
        return state

    def reserve_sandbox_lease_record(
        self,
        request: dict[str, Any],
        *,
        execution_id: str,
        operator_id: str,
        session_id: str,
        capability: CapabilityLeaseBoundary,
        now: str,
    ) -> SandboxLeaseReservation | None:
        if request.get("operation") != "sandbox.create":
            return None
        args = self._validate_request(request)
        key = self._key(request)
        with self._lock:
            prepared = self._prepared.get(key)
        prepared = prepared or self.backend.preflight(self._create_process_request(request))
        profile = prepared.profile
        requested = args.get("ttl_seconds", profile.default_ttl_seconds)
        requested = _integer(requested, "ttl_seconds", minimum=1, maximum=86400)
        now_dt = _parse_timestamp(now)
        capability_expiry = _parse_timestamp(capability.valid_until)
        capability_seconds = int((capability_expiry - now_dt).total_seconds())
        if capability_seconds < 1:
            raise CapabilityDenied("SANDBOX_CAPABILITY_EXPIRES_BEFORE_RESOURCE", capability.lease_id)
        ttl_seconds = min(requested, profile.max_ttl_seconds, capability_seconds)
        expires_at = _timestamp(now_dt + timedelta(seconds=ttl_seconds))
        daemon_digest = self.backend._daemon_identity_digest(prepared.docker.context_endpoint)
        lease = {
            "schemaVersion": "1.0.0",
            "sandboxLeaseId": args["sandbox_lease_id"],
            "profileId": profile.profile_id,
            "operatorId": operator_id,
            "sessionId": session_id,
            "executionContextId": capability.execution_context_id,
            "creationToolExecutionId": execution_id,
            "profileDigest": profile.profile_digest(),
            "imageId": prepared.docker.image_id,
            "securityProfileDigest": "sha256:" + profile.security_profile_digest(),
            "networkPolicyDigest": "sha256:" + profile.network_policy.digest(),
            "filesystemScopeDigest": "sha256:" + profile.filesystem_scope_digest(),
            "persistentEntrypointDigest": profile.persistent_entrypoint_digest(),
            "daemonIdentityDigest": daemon_digest,
            "dockerEndpoint": prepared.docker.context_endpoint,
            "createdAt": now,
            "expiresAt": expires_at,
            "ttlSeconds": ttl_seconds,
            "state": "reserved",
        }
        return SandboxLeaseReservation(args["sandbox_lease_id"], lease)

    def begin_sandbox_close_patch(
        self,
        request: dict[str, Any],
        *,
        operator_id: str,
        session_id: str,
    ) -> SandboxCloseBegin | None:
        if request.get("operation") != "sandbox.close":
            return None
        args = self._validate_request(request)
        state = self._state(args["sandbox_lease_id"])
        if state["operatorId"] != operator_id or state["sessionId"] != session_id:
            raise AuthorityViolation("SANDBOX_OWNER_IDENTITY_MISMATCH")
        if state["state"] == "closed":
            return SandboxCloseBegin(state["sandboxLeaseId"], {}, already_closed=True)
        if state["state"] not in {"created", "running", "indeterminate", "closing"}:
            raise AuthorityViolation(f"sandbox close cannot target state {state['state']}")
        return SandboxCloseBegin(
            state["sandboxLeaseId"],
            {"closeReason": state.get("closeReason") or "operator_requested"},
            already_closed=state["state"] == "closing",
        )

    def sandbox_created_patch(
        self, request: dict[str, Any], side_effect_identity: str
    ) -> SandboxTerminalPatch | None:
        if request.get("operation") != "sandbox.create":
            return None
        key = self._key(request)
        with self._lock:
            identity = self._identities.get(key)
        if identity is None or identity.digest() != side_effect_identity:
            raise AuthorityViolation("SANDBOX_CREATE_OBSERVED_IDENTITY_MISMATCH")
        patch: dict[str, Any] = {
            "containerId": identity.workload_container_id,
            "creationAttestationDigest": identity.creation_attestation_digest,
            "sideEffectIdentity": side_effect_identity,
        }
        if identity.guardian_container_id is not None:
            patch["guardianContainerId"] = identity.guardian_container_id
            patch["guardianImageId"] = identity.guardian_image_id
            patch["networkId"] = identity.internal_network_id
            patch["networkName"] = identity.internal_network_name
        return SandboxTerminalPatch(identity.sandbox_lease_id, patch)

    def sandbox_terminal_patch(
        self, request: dict[str, Any], result: dict[str, Any], *, now: str
    ) -> SandboxTerminalPatch | None:
        operation = request.get("operation")
        args = self._validate_request(request)
        sandbox_lease_id = args["sandbox_lease_id"]
        if operation == "sandbox.create":
            if result["status"] == "indeterminate":
                reason = next(
                    (str(item.get("value")) for item in result.get("output", []) if item.get("name") == "reconciliation"),
                    "sandbox create outcome indeterminate",
                )
                return SandboxTerminalPatch(sandbox_lease_id, {"reconciliationReason": reason[:1024]})
            return SandboxTerminalPatch(sandbox_lease_id, {})
        if operation == "sandbox.close":
            if result["status"] == "indeterminate":
                reason = next(
                    (str(item.get("value")) for item in result.get("output", []) if item.get("name") == "reconciliation"),
                    "sandbox close outcome indeterminate",
                )
                return SandboxTerminalPatch(sandbox_lease_id, {"reconciliationReason": reason[:1024]})
            state = self._state(sandbox_lease_id)
            receipt = next(
                (str(item.get("value")) for item in result.get("output", []) if item.get("name") == "closureReceiptDigest"),
                state.get("closureReceiptDigest"),
            )
            patch: dict[str, Any] = {"closedAt": state.get("closedAt") or now}
            if receipt:
                patch["closureReceiptDigest"] = receipt
            return SandboxTerminalPatch(sandbox_lease_id, patch)
        return None

    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        if request.get("operation") != "sandbox.inspect":
            raise AuthorityViolation("sandbox lifecycle execute() is inspect-only")
        args = self._validate_request(request)
        state = self._state(args["sandbox_lease_id"])
        observation: dict[str, Any] | None = None
        if state["state"] != "closed" and state.get("containerId"):
            try:
                observation = self.backend.inspect_persistent(self._identity_from_state(state))
            except AuthorityViolation as exc:
                observation = {"status": "unverified", "reason": str(exc)}
        return {
            "status": "succeeded",
            "exitCode": None,
            "output": [
                _out("string", "sandboxLeaseId", state["sandboxLeaseId"]),
                _out("string", "state", state["state"]),
                _out("string", "durableLease", json.dumps(state, sort_keys=True, separators=(",", ":"))),
                _out("string", "observation", json.dumps(observation, sort_keys=True, separators=(",", ":"))),
            ],
            "sideEffectIdentity": None,
            "error": None,
        }

    def execute_observed(self, request: dict[str, Any], observe_effect) -> dict[str, Any]:
        operation = request.get("operation")
        if operation == "sandbox.inspect":
            # ToolBroker may prefer execute_observed() based on adapter shape;
            # read-only inspection never publishes an external-effect identity.
            return self.execute(request)
        args = self._validate_request(request)
        key = self._key(request)
        if operation == "sandbox.create":
            with self._lock:
                prepared = self._prepared.pop(key, None)
            process_request = self._create_process_request(request)
            prepared = prepared or self.backend.preflight(process_request)
            identity = self.backend.create_persistent_stopped(
                args["sandbox_lease_id"], process_request, prepared=prepared
            )
            with self._lock:
                self._identities[key] = identity
            side_effect_identity = identity.digest()
            observe_effect(side_effect_identity)
            self.backend.start_persistent(identity)
            return {
                "status": "succeeded",
                "exitCode": 0,
                "output": [
                    _out("string", "sandboxLeaseId", identity.sandbox_lease_id),
                    _out("string", "containerId", identity.workload_container_id),
                    _out("string", "identityDigest", identity.digest()),
                ],
                "sideEffectIdentity": side_effect_identity,
                "error": None,
            }
        if operation != "sandbox.close":
            raise AuthorityViolation(f"unsupported consequential sandbox lifecycle operation: {operation}")
        with self._lock:
            already_closed = key in self._already_closed
            identity = self._identities.get(key)
        if already_closed:
            state = self._state(args["sandbox_lease_id"])
            output = [_out("string", "sandboxLeaseId", state["sandboxLeaseId"])]
            if state.get("closureReceiptDigest"):
                output.append(_out("string", "closureReceiptDigest", state["closureReceiptDigest"]))
            return {"status": "succeeded", "exitCode": 0, "output": output, "sideEffectIdentity": None, "error": None}
        if identity is None:
            state = self._state(args["sandbox_lease_id"])
            if not state.get("containerId"):
                raise AuthorityViolation("SANDBOX_CLOSE_REQUIRES_RECONCILED_RUNTIME_IDENTITY")
            identity = self._identity_from_state(state)
        side_effect_identity = digest(
            {"operation": "sandbox.close", "sandboxLeaseId": identity.sandbox_lease_id, "identityDigest": identity.digest()}
        )
        observe_effect(side_effect_identity)
        closed = self.backend.close_persistent(identity)
        output = [
            _out("string", "sandboxLeaseId", identity.sandbox_lease_id),
            _out("string", "closureReceiptDigest", closed.closure_receipt_digest),
            _out("boolean", "cleanupSucceeded", closed.cleanup_succeeded),
        ]
        if closed.cleanup_error:
            output.append(_out("string", "cleanupError", closed.cleanup_error))
        if not closed.cleanup_succeeded:
            output.append(_out("string", "reconciliation", "sandbox close could not prove exact resource absence"))
        return {
            "status": "succeeded" if closed.cleanup_succeeded else "indeterminate",
            "exitCode": 0 if closed.cleanup_succeeded else None,
            "output": output,
            "sideEffectIdentity": side_effect_identity,
            "error": None,
        }
