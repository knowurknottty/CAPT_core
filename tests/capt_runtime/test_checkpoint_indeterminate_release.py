"""Checkpoint/release gate cannot erase indeterminate external outcomes."""
from __future__ import annotations

from capt_runtime.aggregates import CapabilityAggregate
from capt_runtime.checkpoint import (
    can_dispatch_consequential, create_checkpoint, verify_checkpoint
)


class StubStore:
    """Offline checkpoint fixture with one reconstructed capability stream."""

    def __init__(self, reservation_state):
        self.state = {
            "lease": None,
            "reservations": [{"reservationId": "res-indeterminate-1", "state": reservation_state}],
        }
        self.saved = None

    def all_aggregates(self):
        return [("capability-g-fixture", "capability", 3)]

    def require_state(self, stream_id):
        assert stream_id == "capability-g-fixture"
        return self.state

    def head_sequence(self):
        return 7

    def read_events(self, after_sequence=0):
        assert after_sequence == 6
        return [{"eventId": "event-fixture-head"}]

    def verify_chain(self):
        return "sha256:" + "a" * 64

    def pending_outbox(self):
        return []

    def save_checkpoint(self, manifest):
        self.saved = manifest


def test_indeterminate_reservation_still_blocks_checkpoint_and_release():
    store = StubStore("awaiting_reconciliation")
    assert CapabilityAggregate.open_reservations(store.state) == []
    assert CapabilityAggregate.unresolved_reservations(store.state) == ["res-indeterminate-1"]
    manifest = create_checkpoint(
        store, "cp-fixture-indeterminate", "2026-10-19T00:00:00Z",
        "sha256:" + "b" * 64,
    )
    verify_checkpoint(manifest)
    assert manifest["recoveryState"] == {
        "kind": "awaiting_reconciliation",
        "openReservationIds": ["res-indeterminate-1"],
    }
    assert not can_dispatch_consequential(manifest)
    assert store.saved == manifest


def test_actual_indeterminate_capability_transition_remains_release_blocking():
    """Use the real aggregate transition, not an invented recovered state."""
    state = CapabilityAggregate.grant({
        "grantId": "g-test", "subject": {"actorId": "exec-test"},
        "capabilityId": "cap.fs.write", "operations": ["fs.write"],
        "scope": {"kind": "filesystem", "rootPath": "/tmp/fixture", "recursive": True},
        "policyDecisionId": "pd-test", "policyBundleDigest": "sha256:" + "a" * 64,
        "maxUses": 1, "validFrom": "2026-10-19T00:00:00Z",
        "validUntil": "2026-10-20T00:00:00Z",
    })
    state = CapabilityAggregate.activate_lease(state, {
        "leaseId": "lease-test", "grantId": "g-test", "missionId": "m-test",
        "taskId": "t-test", "executionContextId": "ec-test",
        "operations": ["fs.write"],
        "scope": {"kind": "filesystem", "rootPath": "/tmp/fixture", "recursive": True},
        "maxUses": 1, "validFrom": "2026-10-19T00:00:00Z",
        "validUntil": "2026-10-20T00:00:00Z",
    })
    state = CapabilityAggregate.reserve(state, {
        "reservationId": "res-indeterminate-1", "leaseId": "lease-test",
        "operation": "fs.write", "operationFingerprint": "sha256:" + "b" * 64,
        "idempotencyKey": "dispatch-test",
    }, "2026-10-19T01:00:00Z")
    state = CapabilityAggregate.finalize(state, {
        "consumptionId": "con-test", "reservationId": "res-indeterminate-1",
        "leaseId": "lease-test", "outcome": "indeterminate",
    })
    assert state["usesConsumed"] == 1
    assert state["reservations"][0]["state"] == "awaiting_reconciliation"
    store = StubStore("open")
    store.state = state
    manifest = create_checkpoint(
        store, "cp-after-indeterminate-consumption",
        "2026-10-19T02:00:00Z", "sha256:" + "d" * 64,
    )
    verify_checkpoint(manifest)
    assert manifest["recoveryState"]["kind"] == "awaiting_reconciliation"
    assert not can_dispatch_consequential(manifest)


def test_open_reservation_still_blocks_checkpoint():
    manifest = create_checkpoint(
        StubStore("open"), "cp-fixture-open", "2026-10-19T00:00:00Z",
        "sha256:" + "b" * 64,
    )
    assert manifest["recoveryState"]["kind"] == "awaiting_reconciliation"
    assert not can_dispatch_consequential(manifest)


def test_finalized_reservation_allows_clean_checkpoint():
    store = StubStore("finalized")
    assert CapabilityAggregate.unresolved_reservations(store.state) == []
    manifest = create_checkpoint(
        store, "cp-fixture-final", "2026-10-19T00:00:00Z",
        "sha256:" + "b" * 64,
    )
    assert manifest["recoveryState"] == {"kind": "clean"}
    assert can_dispatch_consequential(manifest)
