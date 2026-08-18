"""Tests for governed out-of-band operator steering (CAPT-UPG-011)."""

import pytest
from capt_runtime.cohort import (
    BoundedCohort, Contribution, ContributionOutcome, DeliberationEpoch,
    EscalationCategory,
)
from capt_runtime.store import EventStore
from desktop.m1_command_service import RuntimeCommandService


def test_operator_steering_epoch_invalidation():
    """Steering directive advances epoch and invalidates prior epoch contributions."""
    epoch = DeliberationEpoch("m-1", "t-1")
    cohort = BoundedCohort({"planner", "critic"}, {"planner", "critic"}, 2, 2)
    
    # Round 0 in Epoch 0: planner and critic submit contributions
    c1 = Contribution("c-1", "planner", 0, 0, ContributionOutcome.CONTRIBUTE, 1)
    c2 = Contribution("c-2", "critic", 0, 0, ContributionOutcome.DISSENT, 1, material=True)
    cohort.record(c1)
    cohort.record(c2)
    
    assert c1.admissible_current(epoch) is True
    assert c2.admissible_current(epoch) is True

    # Operator performs out-of-band steering
    new_epoch = epoch.steer()
    assert new_epoch == 1

    # Old contributions from epoch 0 are no longer admissible in epoch 1
    assert c1.admissible_current(epoch) is False
    assert c2.admissible_current(epoch) is False

    # New contributions in epoch 1 are admitted
    c3 = Contribution("c-3", "planner", 1, 0, ContributionOutcome.PASS, 2)
    c4 = Contribution("c-4", "critic", 1, 0, ContributionOutcome.PASS, 2)
    cohort.record(c3)
    cohort.record(c4)
    assert c3.admissible_current(epoch) is True
    assert c4.admissible_current(epoch) is True
    assert cohort.stopping_reason(epoch) == "SILENCE_QUORUM"


def test_operator_steering_command_service_validation(tmp_path):
    """RuntimeCommandService accepts steer_deliberation with validated operator identity."""
    db = str(tmp_path / "steering.db")
    store = EventStore(db)
    cmd_svc = RuntimeCommandService(store, operator_id="operator-knowurknot", session_id="sess-1")

    cmd = {
        "schemaVersion": "1.0.0",
        "commandId": "cmd-steer-1",
        "operatorId": "operator-knowurknot",
        "sessionId": "sess-1",
        "correlationId": "corr-steer-1",
        "idempotencyKey": "idem-steer-1",
        "timestamp": "2026-08-16T00:00:00Z",
        "op": "steer_deliberation",
        "payload": {
            "cohortId": "coh-active-1",
            "directive": "Pivot analysis towards security closure.",
            "reason": "operator preference",
        },
    }
    receipt = cmd_svc.execute(cmd)
    assert receipt["status"] == "accepted", f"Steer receipt: {receipt}"
    assert receipt["result"]["steeredBy"] == "operator-knowurknot"
    assert receipt["result"]["directive"] == "Pivot analysis towards security closure."
    store.close()
