from __future__ import annotations

import json
from pathlib import Path

import pytest

from capt_runtime import commands
from capt_runtime.aggregates import CapabilityAggregate, SandboxLeaseAggregate
from capt_runtime.contracts import digest
from capt_runtime.errors import AuthorityViolation
from capt_runtime.services import RuntimeService
from capt_runtime.store import AppendRequest, EventStore
from capt_runtime.tool_broker import ToolBroker, tool_request_fingerprint
from capt_runtime.tools.adapters.inversion_sandbox_terminal import (
    InversionSandboxTerminalToolAdapter,
)
from capt_runtime.tools.backends.docker import DockerPreparedTarget
from capt_runtime.tools.backends.inversion_sandbox import (
    InversionSandboxPreparedTarget,
    InversionSandboxProcessBackend,
    InversionSandboxProcessResult,
    InversionSandboxProfile,
    InversionSandboxProfileRegistry,
    PersistentSandboxExecResult,
    SandboxRuntimeIdentity,
)
from capt_runtime.tools.builtins import TERMINAL_INVERSION_SANDBOX_DESCRIPTOR
from capt_runtime.tools.registry import ToolRegistry

NOW = "2026-09-09T12:00:00Z"
IMAGE = "sha256:" + "a" * 64
CONTAINER = "b" * 64


def _profile(profile_id: str = "persistent-exec") -> InversionSandboxProfile:
    return InversionSandboxProfile(
        profile_id=profile_id,
        context_name="desktop-linux",
        image_ref="python:3.13-slim",
        persistent_entrypoint_argv=("/usr/local/bin/python3", "-c", "import time; time.sleep(3600)"),
    )


def _identity(profile: InversionSandboxProfile) -> SandboxRuntimeIdentity:
    return SandboxRuntimeIdentity(
        sandbox_lease_id="sandbox-exec-1",
        profile_id=profile.profile_id,
        profile_digest=profile.profile_digest(),
        context_endpoint="unix:///tmp/docker.sock",
        daemon_identity_digest=digest({"daemon": "exec"}),
        workload_container_id=CONTAINER,
        workload_image_id=IMAGE,
        security_profile_digest="sha256:" + profile.security_profile_digest(),
        network_policy_digest="sha256:" + profile.network_policy.digest(),
        filesystem_scope_digest="sha256:" + profile.filesystem_scope_digest(),
        persistent_entrypoint_digest=profile.persistent_entrypoint_digest(),
        creation_attestation_digest=digest({"attestation": "exec"}),
    )


def _prepared(profile: InversionSandboxProfile) -> InversionSandboxPreparedTarget:
    return InversionSandboxPreparedTarget(
        profile,
        DockerPreparedTarget(profile.docker_profile(), "unix:///tmp/docker.sock", IMAGE, None),
    )


def _meta(name: str, kind: str = "execution_plane") -> dict:
    return commands.command(
        command_id=name,
        idempotency_key=name,
        operation_fingerprint=commands.fingerprint(name, {"name": name}),
        correlation_id="corr-persistent-exec",
        actor_id="actor-persistent-exec",
        actor_kind=kind,
        issued_at=NOW,
    )


def _seed_running_lease(store: EventStore, service: RuntimeService, profile: InversionSandboxProfile) -> dict:
    identity = _identity(profile)
    record = {
        "schemaVersion": "1.0.0",
        "sandboxLeaseId": identity.sandbox_lease_id,
        "profileId": profile.profile_id,
        "operatorId": "operator-1",
        "sessionId": "session-1",
        "executionContextId": "ctx-exec",
        "creationToolExecutionId": "create-exec-1",
        "profileDigest": profile.profile_digest(),
        "imageId": IMAGE,
        "securityProfileDigest": identity.security_profile_digest,
        "networkPolicyDigest": identity.network_policy_digest,
        "filesystemScopeDigest": identity.filesystem_scope_digest,
        "persistentEntrypointDigest": identity.persistent_entrypoint_digest,
        "daemonIdentityDigest": identity.daemon_identity_digest,
        "dockerEndpoint": identity.context_endpoint,
        "createdAt": NOW,
        "expiresAt": "2026-09-09T12:30:00Z",
        "ttlSeconds": 1800,
        "state": "reserved",
    }
    service.reserve_sandbox_lease(record, _meta("reserve-exec-lease"))
    stream = SandboxLeaseAggregate.stream_id(identity.sandbox_lease_id)
    reserved = store.require_state(stream)
    created = SandboxLeaseAggregate.record_created(
        reserved,
        {
            "containerId": identity.workload_container_id,
            "creationAttestationDigest": identity.creation_attestation_digest,
            "sideEffectIdentity": identity.digest(),
            "updatedAt": NOW,
        },
    )
    m1 = _meta("seed-created")
    e1 = service._sandbox_transition_event(reserved, created, m1)
    store.commit_command(
        [AppendRequest(stream, SandboxLeaseAggregate.KIND, store.aggregate_version(stream), e1, created)],
        m1["idempotencyKey"], m1["operationFingerprint"], m1["commandId"],
    )
    running = SandboxLeaseAggregate.record_running(created, {"updatedAt": NOW})
    m2 = _meta("seed-running")
    e2 = service._sandbox_transition_event(created, running, m2)
    store.commit_command(
        [AppendRequest(stream, SandboxLeaseAggregate.KIND, store.aggregate_version(stream), e2, running)],
        m2["idempotencyKey"], m2["operationFingerprint"], m2["commandId"],
    )
    return running


def _seed_capability(store: EventStore, service: RuntimeService) -> tuple[str, str]:
    grant_id, lease_id = "grant-persistent-exec", "lease-persistent-exec"
    grant = {
        "schemaVersion": "1.0.0", "grantId": grant_id,
        "subject": {"actorId": "tool-broker", "kind": "execution_plane"},
        "capabilityId": "cap.terminal.exec", "operations": ["terminal.exec"],
        "scope": {"kind": "filesystem", "rootPath": "/workspace", "recursive": True},
        "policyDecisionId": "pd-persistent-exec", "policyBundleDigest": digest({"policy": "exec"}),
        "conditions": [], "maxUses": 4,
        "validFrom": "2026-09-09T11:00:00Z", "validUntil": "2026-09-09T13:00:00Z",
        "issuedBy": {"actorId": "gk", "kind": "governance_kernel"}, "issuedAt": NOW,
    }
    state = CapabilityAggregate.grant(grant)
    meta = _meta("seed-exec-grant", "governance_kernel")
    stream = CapabilityAggregate.stream_id(grant_id)
    event = commands.envelope(
        event_id=meta["commandId"] + "-ev1", stream_id=stream, event_type="CapabilityGranted",
        payload={"eventType": "CapabilityGranted", "grant": grant}, metadata=meta, occurred_at=NOW,
    )
    store.commit_command(
        [AppendRequest(stream, CapabilityAggregate.KIND, 0, event, state)],
        meta["idempotencyKey"], meta["operationFingerprint"], meta["commandId"],
    )
    service.activate_lease(
        {
            "schemaVersion": "1.0.0", "leaseId": lease_id, "grantId": grant_id,
            "missionId": "mission-exec", "taskId": "task-exec", "executionContextId": "ctx-exec",
            "operations": ["terminal.exec"], "scope": grant["scope"], "maxUses": 4,
            "validFrom": "2026-09-09T11:00:00Z", "validUntil": "2026-09-09T13:00:00Z",
            "activatedAt": NOW,
        },
        _meta("activate-exec-lease", "governance_kernel"),
    )
    return grant_id, lease_id


def _request(grant: str, lease: str, *, idem: str, persistent: bool = True, target: str = "persistent-exec") -> dict:
    args = [
        {"kind": "string", "name": "argv", "value": json.dumps(["/bin/echo", "ok"])},
        {"kind": "path", "name": "cwd", "value": "/workspace"},
    ]
    if persistent:
        args.append({"kind": "string", "name": "sandbox_lease_id", "value": "sandbox-exec-1"})
    request = {
        "schemaVersion": "1.0.0", "toolRequestId": "req-" + idem,
        "toolId": "terminal.inversion_sandbox", "operation": "terminal.exec", "arguments": args,
        "consequential": True, "grantId": grant, "leaseId": lease, "reservationId": None,
        "backendId": "inversion_sandbox", "targetIdentity": target,
        "filesystemScope": "/workspace", "idempotencyKey": idem,
        "operationFingerprint": "sha256:" + "0" * 64, "replayPolicy": "never", "requestedAt": NOW,
    }
    request["operationFingerprint"] = tool_request_fingerprint(request)
    return request


def _setup(tmp_path: Path):
    store = EventStore(str(tmp_path / "runtime.db"))
    service = RuntimeService(store)
    profile = _profile()
    backend = InversionSandboxProcessBackend(InversionSandboxProfileRegistry((profile,)))
    identity = _identity(profile)
    backend.readiness = lambda: {"status": "available", "reason": "fake ready"}
    backend.preflight = lambda _request: _prepared(profile)
    backend.inspect_persistent = lambda _identity: {
        "workloadRunning": True,
        "workloadState": "running",
        "observationDigest": digest({"observation": "exact"}),
    }
    backend.exec_persistent = lambda _identity, **_kwargs: PersistentSandboxExecResult(
        exit_code=0, stdout="ok\n", stderr="", stdout_total_bytes=3, stderr_total_bytes=0,
        stdout_truncated=False, stderr_truncated=False, timed_out=False,
        termination_proven=True, observation_digest=digest({"observation": "exact"}),
    )
    adapter = InversionSandboxTerminalToolAdapter(
        backend,
        lease_resolver=lambda lease_id: store.load_state(SandboxLeaseAggregate.stream_id(lease_id)),
        now=lambda: NOW,
    )
    registry = ToolRegistry()
    registry.register(
        TERMINAL_INVERSION_SANDBOX_DESCRIPTOR, adapter,
        lambda: {"schemaVersion": "1.0.0", "toolId": "terminal.inversion_sandbox", "status": "available", "reason": "ready", "checkedAt": NOW},
    )
    broker = ToolBroker(service, registry, now=lambda: NOW)
    _seed_running_lease(store, service, profile)
    grant, lease = _seed_capability(store, service)
    return store, service, backend, adapter, broker, profile, identity, grant, lease


def test_persistent_exec_requires_explicit_lease_and_observes_before_exec(tmp_path: Path) -> None:
    store, _service, backend, _adapter, broker, _profile_obj, _identity_obj, grant, lease = _setup(tmp_path)
    order: list[str] = []
    backend.inspect_persistent = lambda _identity: (
        order.append("inspect") or {"workloadRunning": True, "workloadState": "running", "observationDigest": digest({"observation": len(order)})}
    )
    def exec_persistent(_identity, **_kwargs):
        _kwargs["observe_effect"](digest({"observation": "exec-pre"}))
        order.append("exec")
        tool = next(state for sid, kind, _ in store.all_aggregates() if kind == "tool_execution" for state in [store.require_state(sid)])
        assert tool["state"] == "effect_observed"
        return PersistentSandboxExecResult(
            exit_code=0, stdout="ok\n", stderr="", stdout_total_bytes=3, stderr_total_bytes=0,
            stdout_truncated=False, stderr_truncated=False, timed_out=False, termination_proven=True,
            observation_digest=digest({"observation": "exec"}),
        )
    backend.exec_persistent = exec_persistent
    try:
        result = broker.execute(_request(grant, lease, idem="persistent-observed"), operator_id="operator-1", session_id="session-1")
        assert result["status"] == "succeeded"
        assert order[-1] == "exec"
        effect = result["result"]["sideEffectIdentity"]
        assert effect and effect != _identity(_profile()).digest()
        assert store.require_state(SandboxLeaseAggregate.stream_id("sandbox-exec-1"))["state"] == "running"
    finally:
        store.close()


def test_persistent_exec_owner_session_expiry_and_profile_are_fail_closed(tmp_path: Path) -> None:
    store, _service, _backend, adapter, broker, _profile_obj, _identity_obj, grant, lease = _setup(tmp_path)
    try:
        with pytest.raises(AuthorityViolation, match="OWNER"):
            broker.execute(_request(grant, lease, idem="owner-bad"), operator_id="operator-2", session_id="session-1")
        with pytest.raises(AuthorityViolation, match="OWNER"):
            broker.execute(_request(grant, lease, idem="session-bad"), operator_id="operator-1", session_id="session-2")
        with pytest.raises(AuthorityViolation, match="PROFILE"):
            broker.execute(_request(grant, lease, idem="profile-bad", target="other-profile"), operator_id="operator-1", session_id="session-1")
        adapter._now = lambda: "2026-09-09T12:30:00Z"
        with pytest.raises(AuthorityViolation, match="EXPIRED"):
            broker.execute(_request(grant, lease, idem="expired-bad"), operator_id="operator-1", session_id="session-1")
    finally:
        store.close()


def test_persistent_exec_live_identity_drift_is_denied_before_dispatch(tmp_path: Path) -> None:
    store, _service, backend, _adapter, broker, _profile_obj, _identity_obj, grant, lease = _setup(tmp_path)
    calls = {"exec": 0}
    backend.inspect_persistent = lambda _identity: (_ for _ in ()).throw(AuthorityViolation("SANDBOX_CONTAINER_IDENTITY_DRIFT"))
    backend.exec_persistent = lambda *_args, **_kwargs: calls.__setitem__("exec", calls["exec"] + 1)
    try:
        result = broker.execute(_request(grant, lease, idem="drift-denied"), operator_id="operator-1", session_id="session-1")
        assert result["status"] == "denied"
        assert calls["exec"] == 0
    finally:
        store.close()


def test_persistent_exec_timeout_quarantines_resource_atomically(tmp_path: Path) -> None:
    store, _service, backend, _adapter, broker, _profile_obj, _identity_obj, grant, lease = _setup(tmp_path)
    def timeout_exec(_identity, **kwargs):
        kwargs["observe_effect"](digest({"observation": "timeout-pre"}))
        return PersistentSandboxExecResult(
            exit_code=None, stdout="", stderr="timeout", stdout_total_bytes=0, stderr_total_bytes=7,
            stdout_truncated=False, stderr_truncated=False, timed_out=True,
            termination_proven=False, observation_digest=digest({"observation": "timeout"}),
        )
    backend.exec_persistent = timeout_exec
    try:
        result = broker.execute(_request(grant, lease, idem="persistent-timeout"), operator_id="operator-1", session_id="session-1")
        assert result["status"] == "indeterminate"
        resource = store.require_state(SandboxLeaseAggregate.stream_id("sandbox-exec-1"))
        assert resource["state"] == "indeterminate"
        assert resource["reconciliationReason"] == "exec_termination_unknown"
        capability = store.require_state(CapabilityAggregate.stream_id(grant))
        assert capability["usesConsumed"] == 1
        tool = store.require_state("tool_execution-" + result["toolExecutionId"])
        assert tool["state"] == "indeterminate"
        assert tool["sideEffectIdentity"] == result["result"]["sideEffectIdentity"]
    finally:
        store.close()


def test_without_sandbox_lease_id_uses_unchanged_one_shot_path(tmp_path: Path) -> None:
    store, _service, backend, _adapter, broker, profile, _identity_obj, grant, lease = _setup(tmp_path)
    calls = {"one_shot": 0, "persistent": 0}
    class DockerResult:
        cleanup_succeeded=True; control_error=""; timed_out=False; exit_code=0; stdout="ok\n"; stderr=""
        stdout_total_bytes=3; stderr_total_bytes=0; stdout_truncated=False; stderr_truncated=False
        profile_id=profile.profile_id; image_id=IMAGE; container_cwd="/workspace"; repo_digest=None
        container_id=CONTAINER; cleanup_error=""
    backend.execute = lambda *_args, **_kwargs: (
        calls.__setitem__("one_shot", calls["one_shot"] + 1)
        or InversionSandboxProcessResult(DockerResult(), None, digest({"oneshot": True}))
    )
    backend.exec_persistent = lambda *_args, **_kwargs: calls.__setitem__("persistent", calls["persistent"] + 1)
    try:
        result = broker.execute(_request(grant, lease, idem="one-shot-compat", persistent=False), operator_id="operator-1", session_id="session-1")
        assert result["status"] == "succeeded"
        assert calls == {"one_shot": 1, "persistent": 0}
        names = {item["name"] for item in result["result"]["output"]}
        assert {"stdout", "stderr", "containerId", "cleanupSucceeded"}.issubset(names)
    finally:
        store.close()
