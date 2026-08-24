from __future__ import annotations

from capt_runtime import commands
from capt_runtime.aggregates import CapabilityAggregate
from capt_runtime.contracts import digest
from capt_runtime.services import RuntimeService
from capt_runtime.store import AppendRequest, EventStore

NOW = "2026-08-19T10:00:00Z"


def _meta(command_id: str, actor_kind: str) -> dict:
    return commands.command(
        command_id=command_id,
        idempotency_key=command_id,
        operation_fingerprint=commands.fingerprint(command_id, {"subject": "capability-test"}),
        correlation_id="corr-capability-idem",
        actor_id="actor-capability-idem",
        actor_kind=actor_kind,
        issued_at=NOW,
    )


def _seed_leased_capability(store: EventStore, service: RuntimeService) -> None:
    grant = {
        "schemaVersion": "1.0.0", "grantId": "grant-idem-1",
        "subject": {"actorId": "tool-broker", "kind": "execution_plane"},
        "capabilityId": "cap.test.write", "operations": ["test.write"],
        "scope": {"kind": "filesystem", "rootPath": "/tmp/work", "recursive": True},
        "policyDecisionId": "pd-idem-1", "policyBundleDigest": digest({"policy": "test"}),
        "conditions": [], "maxUses": 3,
        "validFrom": "2026-08-19T09:00:00Z", "validUntil": "2026-08-19T12:00:00Z",
        "issuedBy": {"actorId": "gk-test", "kind": "governance_kernel"}, "issuedAt": NOW,
    }
    state = CapabilityAggregate.grant(grant)
    metadata = _meta("seed-grant-idem", "governance_kernel")
    stream = CapabilityAggregate.stream_id(grant["grantId"])
    event = commands.envelope(
        event_id="seed-grant-idem-ev1", stream_id=stream,
        event_type="CapabilityGranted",
        payload={"eventType": "CapabilityGranted", "grant": grant},
        metadata=metadata, occurred_at=NOW,
    )
    store.commit_command(
        [AppendRequest(stream, CapabilityAggregate.KIND, 0, event, state)],
        metadata["idempotencyKey"], metadata["operationFingerprint"], metadata["commandId"],
    )
    lease = {
        "schemaVersion": "1.0.0", "leaseId": "lease-idem-1", "grantId": "grant-idem-1",
        "missionId": "mission-idem-1", "taskId": "task-idem-1",
        "executionContextId": "execctx-idem-1", "operations": ["test.write"],
        "scope": {"kind": "filesystem", "rootPath": "/tmp/work", "recursive": True},
        "maxUses": 3, "validFrom": "2026-08-19T09:00:00Z",
        "validUntil": "2026-08-19T12:00:00Z", "activatedAt": NOW,
    }
    service.activate_lease(lease, _meta("activate-lease-idem", "governance_kernel"))


def test_reserve_use_exact_retry_is_idempotent_before_aggregate_transition(tmp_path) -> None:
    store = EventStore(str(tmp_path / "runtime.db"))
    service = RuntimeService(store)
    try:
        _seed_leased_capability(store, service)
        reservation = {
            "schemaVersion": "1.0.0", "reservationId": "reservation-idem-1",
            "leaseId": "lease-idem-1", "operation": "test.write",
            "operationFingerprint": digest({"operation": "test.write"}),
            "idempotencyKey": "effect-idem-1", "state": "open", "reservedAt": NOW,
        }
        metadata = _meta("reserve-use-idem", "execution_plane")
        first = service.reserve_use("grant-idem-1", reservation, metadata)
        second = service.reserve_use("grant-idem-1", reservation, metadata)
        assert first["status"] == "applied"
        assert second["status"] == "idempotent"
        state = store.require_state("capability-grant-idem-1")
        assert len(state["reservations"]) == 1
    finally:
        store.close()


def test_finalize_use_exact_retry_is_idempotent_before_aggregate_transition(tmp_path) -> None:
    store = EventStore(str(tmp_path / "runtime.db"))
    service = RuntimeService(store)
    try:
        _seed_leased_capability(store, service)
        reservation = {
            "schemaVersion": "1.0.0", "reservationId": "reservation-idem-2",
            "leaseId": "lease-idem-1", "operation": "test.write",
            "operationFingerprint": digest({"operation": "test.write", "n": 2}),
            "idempotencyKey": "effect-idem-2", "state": "open", "reservedAt": NOW,
        }
        service.reserve_use(
            "grant-idem-1", reservation, _meta("reserve-use-idem-2", "execution_plane")
        )
        consumption = {
            "schemaVersion": "1.0.0", "consumptionId": "consume-idem-2",
            "reservationId": "reservation-idem-2", "leaseId": "lease-idem-1",
            "outcome": "succeeded", "sideEffectIdentity": "effect-2", "finalizedAt": NOW,
        }
        metadata = _meta("finalize-use-idem", "execution_plane")
        first = service.finalize_use("grant-idem-1", consumption, metadata)
        second = service.finalize_use("grant-idem-1", consumption, metadata)
        assert first["status"] == "applied"
        assert second["status"] == "idempotent"
        state = store.require_state("capability-grant-idem-1")
        assert len(state["consumptions"]) == 1
        assert state["usesConsumed"] == 1
    finally:
        store.close()
