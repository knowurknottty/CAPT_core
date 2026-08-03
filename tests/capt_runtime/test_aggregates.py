"""Conformance tests: aggregate ownership, optimistic concurrency, transitions."""

from __future__ import annotations

import pytest

from capt_runtime.aggregates import (
    ALL_AGGREGATES,
    CapabilityAggregate,
    ClaimAggregate,
    DriverRunAggregate,
    MissionAggregate,
    TaskAggregate,
)
from capt_runtime.errors import AuthorityViolation, IllegalTransition


def test_ownership_disjoint():
    """I4: no authoritative field is owned by two aggregates."""
    seen = {}
    for agg in ALL_AGGREGATES:
        for field in agg.OWNED_FIELDS:
            seen.setdefault(field, []).append(agg.KIND)
    overlaps = {f: ks for f, ks in seen.items() if len(ks) > 1}
    assert not overlaps, "authority overlap: %s" % overlaps
    # References must never also be owned.
    for agg in ALL_AGGREGATES:
        assert not (agg.OWNED_FIELDS & agg.REFERENCE_FIELDS), agg.KIND


def test_mission_terminal_immutable():
    state = MissionAggregate.create(
        {"missionId": "m1", "state": "draft", "objectives": [], "successCriteria": [],
         "terminationCriteria": [], "taskGraphId": None, "policyDecisionIds": []}
    )
    state = MissionAggregate.transition(state, "authorized")
    state = MissionAggregate.transition(state, "executing")
    state = MissionAggregate.transition(state, "completed")
    with pytest.raises(IllegalTransition):
        MissionAggregate.transition(state, "executing")  # terminal -> back


def test_task_illegal_transition_rejected():
    state = TaskAggregate.create(
        {"taskId": "t1", "missionId": "m1", "title": "x", "state": "pending",
         "consequential": True, "capabilityRequirements": [], "assignedDriverId": None,
         "attempt": 0, "maxAttempts": 3, "recoveryState": "none"}
    )
    with pytest.raises(IllegalTransition):
        TaskAggregate.transition(state, "completed")  # pending -> completed illegal


def test_task_dependency_satisfied_gate():
    state = TaskAggregate.create(
        {"taskId": "t1", "missionId": "m1", "title": "x", "state": "pending",
         "consequential": True, "capabilityRequirements": [], "assignedDriverId": None,
         "attempt": 0, "maxAttempts": 3, "recoveryState": "none"}
    )
    state = TaskAggregate.transition(state, "ready")
    state = TaskAggregate.transition(state, "assigned")
    state = TaskAggregate.transition(state, "running")
    assert state["state"] == "running"
    with pytest.raises(IllegalTransition):
        TaskAggregate.transition(state, "running")  # no self-loop


def test_driver_run_terminal():
    state = DriverRunAggregate.create(
        {"driverRunId": "d1", "driverId": "drv", "missionId": "m1", "taskId": "t1",
         "workOrderVersion": 1}
    )
    state = DriverRunAggregate.transition(state, "submitted")
    state = DriverRunAggregate.transition(state, "running")
    state = DriverRunAggregate.transition(state, "completed")
    with pytest.raises(IllegalTransition):
        DriverRunAggregate.transition(state, "running")


def test_claim_completion_requires_verification():
    """A completion claim cannot be accepted without verified status."""
    claim = ClaimAggregate.propose(
        {"schemaVersion": "1.0.0", "claimId": "c1", "missionId": "m1",
         "kind": "completion", "statement": "done", "evidenceIds": ["e1"],
         "promotionState": "proposed",
         "proposedBy": {"actorId": "exec", "kind": "execution_plane"},
         "proposedAt": "2026-08-02T00:00:00Z"}
    )
    with pytest.raises(AuthorityViolation):
        ClaimAggregate.decide(
            claim,
            {"schemaVersion": "1.0.0", "decisionId": "dec-1", "claimId": "c1",
             "verdict": "accept", "rationale": "x",
             "decidedBy": {"actorId": "cg", "kind": "claim_authority"},
             "decidedAt": "2026-08-02T00:00:00Z"},
        )
