from __future__ import annotations

from copy import deepcopy

import pytest

from capt_runtime import commands
from capt_runtime.aggregates import CapabilityAggregate, SandboxLeaseAggregate, ToolExecutionAggregate
from capt_runtime.contracts import digest
from capt_runtime.errors import AuthorityViolation
from capt_runtime.services import RuntimeService
from capt_runtime.store import AppendRequest, EventStore
from tests.capt_runtime.test_sandbox_lease_aggregate import identity_patch, sandbox_lease_fixture

NOW = "2026-09-09T12:00:00Z"


def _meta(command_id: str, actor_kind: str = "execution_plane") -> dict:
    return commands.command(
        command_id=command_id,
        idempotency_key=command_id,
        operation_fingerprint=commands.fingerprint(command_id, {"sandbox": "sandbox-1"}),
        correlation_id="corr-sandbox-service",
        actor_id="exec-sandbox-service",
        actor_kind=actor_kind,
        issued_at=NOW,
    )


def _seed_capability(store: EventStore, service: RuntimeService) -> tuple[dict, dict]:
    grant = {
        "schemaVersion": "1.0.0", "grantId": "grant-sandbox-1",
        "subject": {"actorId": "tool-broker", "kind": "execution_plane"},
        "capabilityId": "cap.sandbox.create", "operations": ["sandbox.create"],
        "scope": {"kind": "tool", "toolIds": ["sandbox.inversion"]},
        "policyDecisionId": "pd-sandbox-service", "policyBundleDigest": digest({"policy": "sandbox"}),
        "conditions": [], "maxUses": 4,
        "validFrom": "2026-09-09T11:00:00Z", "validUntil": "2026-09-09T15:00:00Z",
        "issuedBy": {"actorId": "gk-test", "kind": "governance_kernel"}, "issuedAt": NOW,
    }
    state = CapabilityAggregate.grant(grant)
    meta = _meta("seed-sandbox-cap", "governance_kernel")
    stream = CapabilityAggregate.stream_id(grant["grantId"])
    event = commands.envelope(
        event_id="seed-sandbox-cap-ev1", stream_id=stream, event_type="CapabilityGranted",
        payload={"eventType": "CapabilityGranted", "grant": grant}, metadata=meta, occurred_at=NOW,
    )
    store.commit_command(
        [AppendRequest(stream, CapabilityAggregate.KIND, 0, event, state)],
        meta["idempotencyKey"], meta["operationFingerprint"], meta["commandId"],
    )
    lease = {
        "schemaVersion": "1.0.0", "leaseId": "cap-lease-sandbox-1", "grantId": grant["grantId"],
        "missionId": "mission-sandbox", "taskId": "task-sandbox", "executionContextId": "context-1",
        "operations": ["sandbox.create"], "scope": grant["scope"], "maxUses": 4,
        "validFrom": "2026-09-09T11:00:00Z", "validUntil": "2026-09-09T15:00:00Z",
        "activatedAt": NOW,
    }
    service.activate_lease(lease, _meta("activate-sandbox-cap", "governance_kernel"))
    return grant, lease



def _sandbox_lease(state: str = "reserved") -> dict:
    lease = sandbox_lease_fixture(state)
    lease["creationToolExecutionId"] = "tool-sandbox-create-1"
    return lease


def _reservation() -> dict:
    return {
        "schemaVersion": "1.0.0", "reservationId": "res-sandbox-create-1",
        "leaseId": "cap-lease-sandbox-1", "operation": "sandbox.create",
        "operationFingerprint": digest({"operation": "sandbox.create", "sandbox": "sandbox-1"}),
        "idempotencyKey": "sandbox-effect-1", "state": "open", "reservedAt": NOW,
    }


def _execution() -> dict:
    return {
        "schemaVersion": "1.0.0", "toolExecutionId": "tool-sandbox-create-1",
        "toolRequestId": "tool-req-sandbox-create-1", "operatorId": "operator-1", "sessionId": "session-1",
        "toolId": "sandbox.inversion", "operation": "sandbox.create",
        "operationFingerprint": digest({"operation": "sandbox.create", "sandbox": "sandbox-1"}),
        "descriptorDigest": digest({"toolId": "sandbox.inversion"}),
        "adapterId": "adapter-sandbox-inversion", "backendId": "inversion_sandbox",
        "effectClass": "resource_creation", "consequential": True,
        "grantId": "grant-sandbox-1", "leaseId": "cap-lease-sandbox-1",
        "reservationId": "res-sandbox-create-1", "state": "prepared",
        "dispatchBoundary": "not_started", "result": None, "resultDigest": None,
        "sideEffectIdentity": None, "settlementStatus": "not_settled", "reconciliationReason": None,
        "preparedAt": NOW, "updatedAt": NOW,
    }


def _result(side_effect_identity: str, status: str = "succeeded") -> dict:
    output = [{"kind": "string", "name": "sandboxLeaseId", "value": "sandbox-1"}]
    return {
        "schemaVersion": "1.0.0", "toolResultId": "tool-result-sandbox-create-1",
        "toolRequestId": "tool-req-sandbox-create-1", "status": status,
        "exitCode": 0 if status == "succeeded" else None, "output": output,
        "outputDigest": digest(output), "sideEffectIdentity": side_effect_identity,
        "error": None, "completedAt": NOW,
    }


def _consumption(side_effect_identity: str) -> dict:
    return {
        "schemaVersion": "1.0.0", "consumptionId": "consume-sandbox-create-1",
        "reservationId": "res-sandbox-create-1", "leaseId": "cap-lease-sandbox-1",
        "outcome": "succeeded", "sideEffectIdentity": side_effect_identity, "finalizedAt": NOW,
    }


def _prepare_dispatching(service: RuntimeService) -> None:
    service.prepare_tool_execution(_execution(), _meta("prepare-sandbox-tool"))
    service.transition_tool_execution(
        "tool-sandbox-create-1", "admitted", {"reservationId": "res-sandbox-create-1"},
        _meta("admit-sandbox-tool"),
    )
    service.transition_tool_execution(
        "tool-sandbox-create-1", "dispatching", {"dispatchBoundary": "started"},
        _meta("dispatch-sandbox-tool"),
    )


def test_reserve_sandbox_lease_persists_resource_state(tmp_path) -> None:
    store = EventStore(str(tmp_path / "runtime.db")); service = RuntimeService(store)
    try:
        lease = _sandbox_lease()
        result = service.reserve_sandbox_lease(lease, _meta("reserve-sandbox-lease"))
        assert result["status"] == "applied"
        assert store.require_state(SandboxLeaseAggregate.stream_id("sandbox-1"))["state"] == "reserved"
    finally:
        store.close()


def test_observe_create_effect_commits_tool_and_sandbox_atomically(tmp_path) -> None:
    store = EventStore(str(tmp_path / "runtime.db")); service = RuntimeService(store)
    try:
        _prepare_dispatching(service)
        service.reserve_sandbox_lease(_sandbox_lease(), _meta("reserve-sandbox-lease"))
        patch = identity_patch()
        side_effect_identity = digest({"sandbox": "sandbox-1", "container": patch["containerId"]})
        patch["sideEffectIdentity"] = side_effect_identity
        service.observe_sandbox_create_effect(
            "tool-sandbox-create-1", "sandbox-1", side_effect_identity, patch,
            _meta("observe-sandbox-create"),
        )
        tool = store.require_state(ToolExecutionAggregate.stream_id("tool-sandbox-create-1"))
        lease = store.require_state(SandboxLeaseAggregate.stream_id("sandbox-1"))
        assert tool["state"] == "effect_observed"
        assert tool["sideEffectIdentity"] == side_effect_identity
        assert lease["state"] == "created"
        assert lease["sideEffectIdentity"] == side_effect_identity
        events = store.read_events()
        assert events[-2]["streamId"] == ToolExecutionAggregate.stream_id("tool-sandbox-create-1")
        assert events[-1]["streamId"] == SandboxLeaseAggregate.stream_id("sandbox-1")
    finally:
        store.close()


def test_settle_create_commits_capability_tool_and_running_lease_atomically(tmp_path) -> None:
    store = EventStore(str(tmp_path / "runtime.db")); service = RuntimeService(store)
    try:
        _seed_capability(store, service)
        service.reserve_use("grant-sandbox-1", _reservation(), _meta("reserve-create-use"))
        _prepare_dispatching(service)
        service.reserve_sandbox_lease(_sandbox_lease(), _meta("reserve-sandbox-lease"))
        patch = identity_patch()
        side_effect_identity = digest({"sandbox": "sandbox-1", "container": patch["containerId"]})
        patch["sideEffectIdentity"] = side_effect_identity
        service.observe_sandbox_create_effect(
            "tool-sandbox-create-1", "sandbox-1", side_effect_identity, patch,
            _meta("observe-sandbox-create"),
        )
        result = _result(side_effect_identity)
        service.settle_sandbox_create(
            "grant-sandbox-1", _consumption(side_effect_identity), "tool-sandbox-create-1", "sandbox-1",
            result, {}, _meta("settle-sandbox-create"),
        )
        capability = store.require_state(CapabilityAggregate.stream_id("grant-sandbox-1"))
        tool = store.require_state(ToolExecutionAggregate.stream_id("tool-sandbox-create-1"))
        lease = store.require_state(SandboxLeaseAggregate.stream_id("sandbox-1"))
        assert capability["usesConsumed"] == 1
        assert tool["state"] == "completed" and tool["settlementStatus"] == "settled"
        assert lease["state"] == "running"
    finally:
        store.close()


def test_settle_create_rejects_mismatched_capability_or_sandbox_identity(tmp_path) -> None:
    store = EventStore(str(tmp_path / "runtime.db")); service = RuntimeService(store)
    try:
        _seed_capability(store, service)
        service.reserve_use("grant-sandbox-1", _reservation(), _meta("reserve-create-use"))
        _prepare_dispatching(service)
        service.reserve_sandbox_lease(_sandbox_lease(), _meta("reserve-sandbox-lease"))
        patch = identity_patch(); side_effect_identity = digest({"sandbox": "sandbox-1"})
        patch["sideEffectIdentity"] = side_effect_identity
        service.observe_sandbox_create_effect(
            "tool-sandbox-create-1", "sandbox-1", side_effect_identity, patch,
            _meta("observe-sandbox-create"),
        )
        bad = deepcopy(_consumption(side_effect_identity)); bad["leaseId"] = "wrong-capability-lease"
        with pytest.raises(AuthorityViolation):
            service.settle_sandbox_create(
                "grant-sandbox-1", bad, "tool-sandbox-create-1", "sandbox-1",
                _result(side_effect_identity), {}, _meta("settle-sandbox-bad-cap"),
            )
        with pytest.raises(AuthorityViolation):
            service.settle_sandbox_create(
                "grant-sandbox-1", _consumption(side_effect_identity), "tool-sandbox-create-1", "sandbox-other",
                _result(side_effect_identity), {}, _meta("settle-sandbox-bad-id"),
            )
    finally:
        store.close()


def test_lifecycle_commands_support_close_indeterminate_and_reconciliation(tmp_path) -> None:
    store = EventStore(str(tmp_path / "runtime.db")); service = RuntimeService(store)
    try:
        state = _sandbox_lease("running")
        meta = _meta("seed-running-sandbox")
        stream = SandboxLeaseAggregate.stream_id("sandbox-1")
        event = commands.envelope(
            event_id="seed-running-sandbox-ev1", stream_id=stream, event_type="SandboxLeaseReserved",
            payload={"eventType": "SandboxLeaseReserved", "lease": _sandbox_lease()},
            metadata=meta, occurred_at=NOW,
        )
        store.commit_command(
            [AppendRequest(stream, SandboxLeaseAggregate.KIND, 0, event, state)],
            meta["idempotencyKey"], meta["operationFingerprint"], meta["commandId"],
        )
        service.begin_sandbox_close("sandbox-1", {"closeReason": "operator_requested"}, _meta("begin-close"))
        assert store.require_state(stream)["state"] == "closing"
        service.mark_sandbox_indeterminate(
            "sandbox-1", {"reconciliationReason": "close_unknown"}, _meta("mark-close-unknown")
        )
        assert store.require_state(stream)["state"] == "indeterminate"
        service.reconcile_sandbox_lease(
            "sandbox-1", "closing", {"lastReconciledAt": NOW, "reconciliationReason": "close_pending"},
            _meta("reconcile-close"),
        )
        service.record_sandbox_closed(
            "sandbox-1", {"closedAt": NOW, "closureReceiptDigest": digest({"closed": "sandbox-1"})},
            _meta("record-closed"),
        )
        assert store.require_state(stream)["state"] == "closed"
    finally:
        store.close()
