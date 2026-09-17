from __future__ import annotations

from pathlib import Path

import pytest

from capt_runtime import commands
from capt_runtime.aggregates import CapabilityAggregate, SandboxLeaseAggregate
from capt_runtime.contracts import digest
from capt_runtime.errors import AuthorityViolation, CapabilityDenied
from capt_runtime.services import RuntimeService
from capt_runtime.store import AppendRequest, EventStore
from capt_runtime.tool_broker import ToolBroker, tool_request_fingerprint
from capt_runtime.tools.backends.docker import DockerPreparedTarget
from capt_runtime.tools.backends.inversion_sandbox import (
    InversionSandboxPreparedTarget,
    InversionSandboxProcessBackend,
    InversionSandboxProfile,
    InversionSandboxProfileRegistry,
    PersistentSandboxCloseResult,
    SandboxRuntimeIdentity,
)
from capt_runtime.tools.registry import ToolRegistry

NOW = "2026-09-09T12:00:00Z"
IMAGE = "sha256:" + "a" * 64
CONTAINER = "b" * 64


def _profile() -> InversionSandboxProfile:
    return InversionSandboxProfile(
        profile_id="persistent-life",
        context_name="desktop-linux",
        image_ref="python:3.13-slim",
        persistent_entrypoint_argv=("/usr/local/bin/python3", "-c", "import time; time.sleep(3600)"),
        default_ttl_seconds=1800,
        max_ttl_seconds=3600,
    )


def _prepared(profile: InversionSandboxProfile) -> InversionSandboxPreparedTarget:
    return InversionSandboxPreparedTarget(
        profile,
        DockerPreparedTarget(profile.docker_profile(), "unix:///tmp/docker.sock", IMAGE, None),
    )


def _identity(profile: InversionSandboxProfile) -> SandboxRuntimeIdentity:
    return SandboxRuntimeIdentity(
        sandbox_lease_id="sandbox-life-1",
        profile_id=profile.profile_id,
        profile_digest=profile.profile_digest(),
        context_endpoint="unix:///tmp/docker.sock",
        daemon_identity_digest=digest({"daemon": "one"}),
        workload_container_id=CONTAINER,
        workload_image_id=IMAGE,
        security_profile_digest="sha256:" + profile.security_profile_digest(),
        network_policy_digest="sha256:" + profile.network_policy.digest(),
        filesystem_scope_digest="sha256:" + profile.filesystem_scope_digest(),
        persistent_entrypoint_digest=profile.persistent_entrypoint_digest(),
        creation_attestation_digest=digest({"attestation": "one"}),
    )


def _meta(name: str, kind: str = "governance_kernel") -> dict:
    return commands.command(
        command_id=name,
        idempotency_key=name,
        operation_fingerprint=commands.fingerprint(name, {"name": name}),
        correlation_id="corr-life",
        actor_id="actor-life",
        actor_kind=kind,
        issued_at=NOW,
    )


def _seed_capability(store: EventStore, service: RuntimeService, operations: list[str], *, valid_until="2026-09-09T12:20:00Z") -> tuple[str, str]:
    grant_id = "grant-life-" + operations[0].replace(".", "-")
    lease_id = "lease-life-" + operations[0].replace(".", "-")
    grant = {
        "schemaVersion": "1.0.0", "grantId": grant_id,
        "subject": {"actorId": "tool-broker", "kind": "execution_plane"},
        "capabilityId": "cap." + operations[0], "operations": operations,
        "scope": {"kind": "tool", "toolIds": ["sandbox.inversion"]},
        "policyDecisionId": "pd-life", "policyBundleDigest": digest({"policy": "life"}),
        "conditions": [], "maxUses": 10,
        "validFrom": "2026-09-09T11:00:00Z", "validUntil": valid_until,
        "issuedBy": {"actorId": "gk-life", "kind": "governance_kernel"}, "issuedAt": NOW,
    }
    state = CapabilityAggregate.grant(grant)
    meta = _meta("seed-" + grant_id)
    stream = CapabilityAggregate.stream_id(grant_id)
    event = commands.envelope(
        event_id=meta["commandId"] + "-ev1", stream_id=stream, event_type="CapabilityGranted",
        payload={"eventType": "CapabilityGranted", "grant": grant}, metadata=meta, occurred_at=NOW,
    )
    store.commit_command(
        [AppendRequest(stream, CapabilityAggregate.KIND, 0, event, state)],
        meta["idempotencyKey"], meta["operationFingerprint"], meta["commandId"],
    )
    lease = {
        "schemaVersion": "1.0.0", "leaseId": lease_id, "grantId": grant_id,
        "missionId": "mission-life", "taskId": "task-life", "executionContextId": "ctx-life",
        "operations": operations, "scope": grant["scope"], "maxUses": 10,
        "validFrom": "2026-09-09T11:00:00Z", "validUntil": valid_until, "activatedAt": NOW,
    }
    service.activate_lease(lease, _meta("activate-" + lease_id))
    return grant_id, lease_id


def _request(operation: str, grant_id: str | None, lease_id: str | None, *, idem: str, ttl: int | None = None) -> dict:
    args = [{"kind": "string", "name": "sandbox_lease_id", "value": "sandbox-life-1"}]
    if ttl is not None:
        args.append({"kind": "integer", "name": "ttl_seconds", "value": ttl})
    request = {
        "schemaVersion": "1.0.0", "toolRequestId": "req-" + idem,
        "toolId": "sandbox.inversion", "operation": operation, "arguments": args,
        "consequential": operation != "sandbox.inspect",
        "grantId": grant_id, "leaseId": lease_id, "reservationId": None,
        "backendId": "inversion_sandbox", "targetIdentity": "persistent-life",
        "filesystemScope": "/workspace", "idempotencyKey": idem,
        "operationFingerprint": "sha256:" + "0" * 64, "replayPolicy": "never", "requestedAt": NOW,
    }
    request["operationFingerprint"] = tool_request_fingerprint(request)
    return request


def _setup(tmp_path: Path):
    from capt_runtime.tools.adapters.inversion_sandbox_lifecycle import (
        InversionSandboxLifecycleToolAdapter,
    )
    from capt_runtime.tools.builtins import SANDBOX_INVERSION_DESCRIPTOR

    store = EventStore(str(tmp_path / "runtime.db"))
    service = RuntimeService(store)
    profile = _profile()
    backend = InversionSandboxProcessBackend(InversionSandboxProfileRegistry((profile,)))
    prepared = _prepared(profile)
    identity = _identity(profile)
    backend.readiness = lambda: {"status": "available", "reason": "fake ready"}
    backend.preflight = lambda _req: prepared
    backend._daemon_identity_digest = lambda _endpoint: identity.daemon_identity_digest
    backend.create_persistent_stopped = lambda *_args, **_kwargs: identity
    backend.start_persistent = lambda _identity: {"workloadRunning": True, "observationDigest": digest({"running": True})}
    backend.inspect_persistent = lambda _identity: {"workloadRunning": True, "workloadState": "running", "observationDigest": digest({"running": True})}
    backend.close_persistent = lambda _identity: PersistentSandboxCloseResult(True, digest({"closed": True}))
    adapter = InversionSandboxLifecycleToolAdapter(backend, store)
    registry = ToolRegistry()
    registry.register(
        SANDBOX_INVERSION_DESCRIPTOR,
        adapter,
        lambda: {"schemaVersion": "1.0.0", "toolId": "sandbox.inversion", "status": "available", "reason": "ready", "checkedAt": NOW},
    )
    broker = ToolBroker(service, registry, now=lambda: NOW)
    return store, service, backend, adapter, broker, profile


def test_create_is_durable_before_effect_and_ttl_is_capped_by_profile_and_capability(tmp_path: Path) -> None:
    store, service, _backend, _adapter, broker, _profile_obj = _setup(tmp_path)
    try:
        grant, lease = _seed_capability(store, service, ["sandbox.create"])
        result = broker.execute(
            _request("sandbox.create", grant, lease, idem="life-create", ttl=7200),
            operator_id="operator-1", session_id="session-1",
        )
        assert result["status"] == "succeeded"
        resource = store.require_state(SandboxLeaseAggregate.stream_id("sandbox-life-1"))
        assert resource["state"] == "running"
        assert resource["ttlSeconds"] == 1200
        assert resource["expiresAt"] == "2026-09-09T12:20:00Z"
        assert resource["operatorId"] == "operator-1" and resource["sessionId"] == "session-1"
        tool_events = store.read_stream("tool_execution-" + result["toolExecutionId"])
        sandbox_events = store.read_stream(SandboxLeaseAggregate.stream_id("sandbox-life-1"))
        assert sandbox_events[0]["eventType"] == "SandboxLeaseReserved"
        assert any(event["eventType"] == "ToolExecutionEffectObserved" for event in tool_events)
        assert sandbox_events[-1]["payload"]["lease"]["state"] == "running"
        capability = store.require_state(CapabilityAggregate.stream_id(grant))
        assert capability["usesConsumed"] == 1
    finally:
        store.close()


def test_inspect_is_pure_and_owner_bound(tmp_path: Path) -> None:
    store, service, _backend, _adapter, broker, _profile_obj = _setup(tmp_path)
    try:
        create_grant, create_lease = _seed_capability(store, service, ["sandbox.create"])
        broker.execute(_request("sandbox.create", create_grant, create_lease, idem="life-create-owner"), operator_id="operator-1", session_id="session-1")
        inspect_grant, inspect_lease = _seed_capability(store, service, ["sandbox.inspect"])
        request = _request("sandbox.inspect", inspect_grant, inspect_lease, idem="life-inspect")
        ok = broker.execute(request, operator_id="operator-1", session_id="session-1")
        assert ok["status"] == "succeeded"
        assert ok["result"]["sideEffectIdentity"] is None
        with pytest.raises(AuthorityViolation):
            broker.execute(_request("sandbox.inspect", inspect_grant, inspect_lease, idem="life-inspect-wrong"), operator_id="operator-2", session_id="session-1")
    finally:
        store.close()


def test_close_transitions_running_to_closed_and_repeat_close_does_not_mutate_docker(tmp_path: Path) -> None:
    store, service, backend, _adapter, broker, _profile_obj = _setup(tmp_path)
    calls = {"close": 0}
    original = backend.close_persistent
    backend.close_persistent = lambda identity: (calls.__setitem__("close", calls["close"] + 1) or original(identity))
    try:
        create_grant, create_lease = _seed_capability(store, service, ["sandbox.create"])
        broker.execute(_request("sandbox.create", create_grant, create_lease, idem="life-create-close"), operator_id="operator-1", session_id="session-1")
        close_grant, close_lease = _seed_capability(store, service, ["sandbox.close"])
        first = broker.execute(_request("sandbox.close", close_grant, close_lease, idem="life-close-1"), operator_id="operator-1", session_id="session-1")
        assert first["status"] == "succeeded"
        assert store.require_state(SandboxLeaseAggregate.stream_id("sandbox-life-1"))["state"] == "closed"
        second = broker.execute(_request("sandbox.close", close_grant, close_lease, idem="life-close-2"), operator_id="operator-1", session_id="session-1")
        assert second["status"] == "succeeded"
        assert calls["close"] == 1
    finally:
        store.close()


def test_close_requires_its_own_live_capability(tmp_path: Path) -> None:
    store, service, _backend, _adapter, broker, _profile_obj = _setup(tmp_path)
    try:
        create_grant, create_lease = _seed_capability(store, service, ["sandbox.create"])
        broker.execute(_request("sandbox.create", create_grant, create_lease, idem="life-create-cap"), operator_id="operator-1", session_id="session-1")
        with pytest.raises(CapabilityDenied):
            broker.execute(_request("sandbox.close", None, None, idem="life-close-no-cap"), operator_id="operator-1", session_id="session-1")
    finally:
        store.close()


def test_create_failure_after_dispatch_before_identity_quarantines_reserved_lease(tmp_path: Path) -> None:
    store, service, backend, _adapter, broker, _profile_obj = _setup(tmp_path)
    backend.create_persistent_stopped = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("create control path lost"))
    try:
        grant, lease = _seed_capability(store, service, ["sandbox.create"])
        result = broker.execute(_request("sandbox.create", grant, lease, idem="life-create-unknown"), operator_id="operator-1", session_id="session-1")
        assert result["status"] == "indeterminate"
        resource = store.require_state(SandboxLeaseAggregate.stream_id("sandbox-life-1"))
        assert resource["state"] == "indeterminate"
        assert resource.get("containerId") is None
        capability = store.require_state(CapabilityAggregate.stream_id(grant))
        assert capability["usesConsumed"] == 1
    finally:
        store.close()


def test_close_from_indeterminate_with_bound_identity_uses_explicit_reconciliation(tmp_path: Path) -> None:
    store, service, backend, _adapter, broker, _profile_obj = _setup(tmp_path)
    calls = {"close": 0}
    original = backend.close_persistent
    backend.close_persistent = lambda identity: (
        calls.__setitem__("close", calls["close"] + 1) or original(identity)
    )
    try:
        create_grant, create_lease = _seed_capability(store, service, ["sandbox.create"])
        created = broker.execute(
            _request("sandbox.create", create_grant, create_lease, idem="life-create-indeterminate"),
            operator_id="operator-1", session_id="session-1",
        )
        assert created["status"] == "succeeded"
        service.mark_sandbox_indeterminate(
            "sandbox-life-1",
            {"reconciliationReason": "runtime_state_unknown"},
            _meta("mark-life-indeterminate", "execution_plane"),
        )
        close_grant, close_lease = _seed_capability(store, service, ["sandbox.close"])
        closed = broker.execute(
            _request("sandbox.close", close_grant, close_lease, idem="life-close-indeterminate"),
            operator_id="operator-1", session_id="session-1",
        )
        assert closed["status"] == "succeeded"
        assert store.require_state(SandboxLeaseAggregate.stream_id("sandbox-life-1"))["state"] == "closed"
        assert calls["close"] == 1
    finally:
        store.close()
