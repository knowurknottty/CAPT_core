"""Conformance tests: capability lifecycle (spec invariant 7, ledger D/E/I)."""

from __future__ import annotations

import pytest

from capt_runtime.aggregates import CapabilityAggregate, scope_contains
from capt_runtime.errors import CapabilityDenied, IllegalTransition

GRANT = {
    "grantId": "g1", "capabilityId": "cap.fs.write", "subjectActorId": "exec",
    "operations": ["fs.write"],
    "scope": {"kind": "filesystem", "rootPath": "/tmp/w", "recursive": True},
    "conditions": [], "policyDecisionId": "pd1", "policyBundleDigest": "d",
    "maxUses": 2, "usesConsumed": 0,
    "validFrom": "2026-08-02T00:00:00Z", "validUntil": "2026-08-02T06:00:00Z",
    "lease": None, "reservations": [], "consumptions": [], "revocation": None,
}


def _granted():
    return CapabilityAggregate.grant(
        {"grantId": "g1", "subject": {"actorId": "exec"}, "capabilityId": "cap.fs.write",
         "operations": ["fs.write"],
         "scope": {"kind": "filesystem", "rootPath": "/tmp/w", "recursive": True},
         "policyDecisionId": "pd1", "policyBundleDigest": "d", "maxUses": 2,
         "validFrom": "2026-08-02T00:00:00Z", "validUntil": "2026-08-02T06:00:00Z",
         "issuedBy": {"actorId": "gk", "kind": "governance_kernel"}}
    )


def test_scope_narrow_ok():
    assert scope_contains(
        {"kind": "filesystem", "rootPath": "/tmp/w", "recursive": True},
        {"kind": "filesystem", "rootPath": "/tmp/w/sub", "recursive": False},
    )


def test_scope_sibling_blocked():
    assert not scope_contains(
        {"kind": "filesystem", "rootPath": "/tmp/w", "recursive": True},
        {"kind": "filesystem", "rootPath": "/tmp/wa", "recursive": False},
    )


def test_valid_grant_and_lease():
    state = _granted()
    lease = {
        "leaseId": "l1", "grantId": "g1", "missionId": "m1", "taskId": "t1",
        "executionContextId": "ec1", "operations": ["fs.write"],
        "scope": {"kind": "filesystem", "rootPath": "/tmp/w/sub", "recursive": False},
        "maxUses": 1, "validFrom": "2026-08-02T00:01:00Z",
        "validUntil": "2026-08-02T05:00:00Z",
    }
    state = CapabilityAggregate.activate_lease(state, lease)
    assert state["grantState"] == "leased"
    assert state["lease"]["leaseId"] == "l1"


def test_scope_mismatch_rejected():
    state = _granted()
    lease = {
        "leaseId": "l1", "grantId": "g1", "missionId": "m1", "taskId": "t1",
        "executionContextId": "ec1", "operations": ["fs.write"],
        "scope": {"kind": "filesystem", "rootPath": "/tmp/elsewhere", "recursive": False},
        "maxUses": 1, "validFrom": "2026-08-02T00:01:00Z",
        "validUntil": "2026-08-02T05:00:00Z",
    }
    with pytest.raises(CapabilityDenied):
        CapabilityAggregate.activate_lease(state, lease)


def test_lease_widening_operations_rejected():
    state = _granted()
    lease = {
        "leaseId": "l1", "grantId": "g1", "missionId": "m1", "taskId": "t1",
        "executionContextId": "ec1", "operations": ["fs.write", "fs.delete"],
        "scope": {"kind": "filesystem", "rootPath": "/tmp/w/sub", "recursive": False},
        "maxUses": 1, "validFrom": "2026-08-02T00:01:00Z",
        "validUntil": "2026-08-02T05:00:00Z",
    }
    with pytest.raises(CapabilityDenied):
        CapabilityAggregate.activate_lease(state, lease)


def test_revocation_blocks_use():
    state = _granted()
    lease = {
        "leaseId": "l1", "grantId": "g1", "missionId": "m1", "taskId": "t1",
        "executionContextId": "ec1", "operations": ["fs.write"],
        "scope": {"kind": "filesystem", "rootPath": "/tmp/w/sub", "recursive": False},
        "maxUses": 1, "validFrom": "2026-08-02T00:01:00Z",
        "validUntil": "2026-08-02T05:00:00Z",
    }
    state = CapabilityAggregate.activate_lease(state, lease)
    state = CapabilityAggregate.revoke(
        state,
        {"revocationId": "r1", "targetKind": "grant", "targetId": "g1",
         "reason": "incident", "revokedBy": {"actorId": "gk", "kind": "governance_kernel"}},
    )
    with pytest.raises(CapabilityDenied):
        CapabilityAggregate.check_lease(state, "l1", "fs.write",
                                        {"kind": "filesystem", "rootPath": "/tmp/w/sub",
                                         "recursive": False}, "2026-08-02T00:02:00Z")


def test_expiration_blocks_use():
    state = _granted()
    with pytest.raises(CapabilityDenied):
        CapabilityAggregate.check_lease(state, "l1", "fs.write",
                                        {"kind": "filesystem", "rootPath": "/tmp/w/sub",
                                         "recursive": False}, "2026-08-02T07:00:00Z")


def test_max_use_exhaustion():
    state = _granted()
    lease = {
        "leaseId": "l1", "grantId": "g1", "missionId": "m1", "taskId": "t1",
        "executionContextId": "ec1", "operations": ["fs.write"],
        "scope": {"kind": "filesystem", "rootPath": "/tmp/w/sub", "recursive": False},
        "maxUses": 1, "validFrom": "2026-08-02T00:01:00Z",
        "validUntil": "2026-08-02T05:00:00Z",
    }
    state = CapabilityAggregate.activate_lease(state, lease)
    now = "2026-08-02T00:02:00Z"
    CapabilityAggregate.check_lease(state, "l1", "fs.write",
                                    {"kind": "filesystem", "rootPath": "/tmp/w/sub",
                                     "recursive": False}, now)
    res = {"reservationId": "res1", "leaseId": "l1", "operation": "fs.write",
           "operationFingerprint": "fp1", "idempotencyKey": "idem1"}
    state = CapabilityAggregate.reserve(state, res, now)
    state = CapabilityAggregate.finalize(
        state, {"consumptionId": "con1", "reservationId": "res1", "leaseId": "l1",
                "outcome": "succeeded"}
    )
    assert state["grantState"] == "consumed"
    with pytest.raises(CapabilityDenied):
        CapabilityAggregate.check_lease(state, "l1", "fs.write",
                                        {"kind": "filesystem", "rootPath": "/tmp/w/sub",
                                         "recursive": False}, now)


def test_reservation_finalization():
    state = _granted()
    lease = {
        "leaseId": "l1", "grantId": "g1", "missionId": "m1", "taskId": "t1",
        "executionContextId": "ec1", "operations": ["fs.write"],
        "scope": {"kind": "filesystem", "rootPath": "/tmp/w/sub", "recursive": False},
        "maxUses": 2, "validFrom": "2026-08-02T00:01:00Z",
        "validUntil": "2026-08-02T05:00:00Z",
    }
    state = CapabilityAggregate.activate_lease(state, lease)
    now = "2026-08-02T00:02:00Z"
    res = {"reservationId": "res1", "leaseId": "l1", "operation": "fs.write",
           "operationFingerprint": "fp1", "idempotencyKey": "idem1"}
    state = CapabilityAggregate.reserve(state, res, now)
    assert any(r["state"] == "open" for r in state["reservations"])
    state = CapabilityAggregate.finalize(
        state, {"consumptionId": "con-res", "reservationId": "res1", "leaseId": "l1",
                "outcome": "succeeded"}
    )
    assert state["usesConsumed"] == 1
    assert all(r["state"] == "finalized" for r in state["reservations"])


def test_duplicate_consumption_rejected():
    state = _granted()
    lease = {
        "leaseId": "l1", "grantId": "g1", "missionId": "m1", "taskId": "t1",
        "executionContextId": "ec1", "operations": ["fs.write"],
        "scope": {"kind": "filesystem", "rootPath": "/tmp/w/sub", "recursive": False},
        "maxUses": 2, "validFrom": "2026-08-02T00:01:00Z",
        "validUntil": "2026-08-02T05:00:00Z",
    }
    state = CapabilityAggregate.activate_lease(state, lease)
    now = "2026-08-02T00:02:00Z"
    res = {"reservationId": "res1", "leaseId": "l1", "operation": "fs.write",
           "operationFingerprint": "fp1", "idempotencyKey": "idem1"}
    state = CapabilityAggregate.reserve(state, res, now)
    state = CapabilityAggregate.finalize(
        state, {"consumptionId": "con-dup", "reservationId": "res1", "leaseId": "l1",
                "outcome": "succeeded"}
    )
    with pytest.raises(CapabilityDenied):
        CapabilityAggregate.finalize(
            state, {"reservationId": "res1", "leaseId": "l1", "outcome": "succeeded"}
        )


def test_indeterminate_not_retried():
    """An indeterminate outcome leaves the reservation awaiting reconciliation
    and does NOT free the use, so a blind retry is impossible."""
    state = _granted()
    lease = {
        "leaseId": "l1", "grantId": "g1", "missionId": "m1", "taskId": "t1",
        "executionContextId": "ec1", "operations": ["fs.write"],
        "scope": {"kind": "filesystem", "rootPath": "/tmp/w/sub", "recursive": False},
        "maxUses": 1, "validFrom": "2026-08-02T00:01:00Z",
        "validUntil": "2026-08-02T05:00:00Z",
    }
    state = CapabilityAggregate.activate_lease(state, lease)
    now = "2026-08-02T00:02:00Z"
    res = {"reservationId": "res1", "leaseId": "l1", "operation": "fs.write",
           "operationFingerprint": "fp1", "idempotencyKey": "idem1"}
    state = CapabilityAggregate.reserve(state, res, now)
    state = CapabilityAggregate.finalize(
        state, {"consumptionId": "con-ind", "reservationId": "res1", "leaseId": "l1",
                "outcome": "indeterminate"}
    )
    assert state["usesConsumed"] == 1  # counted
    assert state["reservations"][0]["state"] == "awaiting_reconciliation"
    # A second attempt with the same idempotency key is rejected (open holder).
    with pytest.raises(CapabilityDenied):
        CapabilityAggregate.reserve(
            state,
            {"reservationId": "res2", "leaseId": "l1", "operation": "fs.write",
             "operationFingerprint": "fp1", "idempotencyKey": "idem1"},
            now,
        )


def test_revocation_is_terminal():
    state = _granted()
    state = CapabilityAggregate.revoke(
        state,
        {"revocationId": "r1", "targetKind": "grant", "targetId": "g1",
         "reason": "x", "revokedBy": {"actorId": "gk", "kind": "governance_kernel"}},
    )
    with pytest.raises(IllegalTransition):
        CapabilityAggregate.revoke(
            state,
            {"revocationId": "r2", "targetKind": "grant", "targetId": "g1",
             "reason": "y", "revokedBy": {"actorId": "gk", "kind": "governance_kernel"}},
        )
