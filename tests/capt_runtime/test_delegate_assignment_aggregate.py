from __future__ import annotations

import pytest

from capt_runtime.errors import AuthorityViolation, IllegalTransition

NOW = "2026-09-08T17:00:00Z"
LATER = "2026-09-08T18:00:00Z"


def _actor(kind="cognitive_plane"):
    return {"actorId": "researcher", "kind": kind, "displayName": None}


def _spec(**overrides):
    value = {"assignmentId": "da-1", "parentBotId": "researcher",
        "delegateBotId": "delegate-1", "missionId": "m1", "taskId": None,
        "depth": 1, "state": "active", "createdAt": NOW, "expiresAt": LATER,
        "createdBy": _actor(), "lastTransitionAt": NOW, "transitionReason": None}
    value.update(overrides)
    return value


def test_delegate_assignment_requires_future_expiry():
    from capt_runtime.aggregates.delegate_assignment import DelegateAssignmentAggregate
    with pytest.raises(AuthorityViolation, match="DELEGATE_EXPIRY_NOT_AFTER_CREATION"):
        DelegateAssignmentAggregate.create(_spec(expiresAt=NOW))


def test_delegate_assignment_terminal_states_do_not_reopen():
    from capt_runtime.aggregates.delegate_assignment import DelegateAssignmentAggregate
    state = DelegateAssignmentAggregate.create(_spec())
    state = DelegateAssignmentAggregate.transition(
        state, "completed", _actor("system"), "work handed back", LATER)
    assert state["state"] == "completed"
    with pytest.raises(IllegalTransition):
        DelegateAssignmentAggregate.transition(
            state, "active", _actor("system"), "reopen", LATER)


def test_delegate_assignment_cannot_start_terminal():
    from capt_runtime.aggregates.delegate_assignment import DelegateAssignmentAggregate
    with pytest.raises(AuthorityViolation, match="DELEGATE_ASSIGNMENT_MUST_START_ACTIVE"):
        DelegateAssignmentAggregate.create(_spec(state="completed"))


def test_delegate_revocation_and_expiry_require_authority():
    from capt_runtime.aggregates.delegate_assignment import DelegateAssignmentAggregate
    state = DelegateAssignmentAggregate.create(_spec())
    with pytest.raises(AuthorityViolation, match="DELEGATE_REVOCATION_REQUIRES_AUTHORITY"):
        DelegateAssignmentAggregate.transition(
            state, "revoked", _actor("cognitive_plane"), "self revoke", LATER)
    with pytest.raises(AuthorityViolation, match="DELEGATE_EXPIRY_REQUIRES_SYSTEM"):
        DelegateAssignmentAggregate.transition(
            state, "expired", _actor("human"), "looks expired", LATER)


def test_delegate_completion_may_be_reported_by_cognitive_plane():
    from capt_runtime.aggregates.delegate_assignment import DelegateAssignmentAggregate
    state = DelegateAssignmentAggregate.create(_spec())
    state = DelegateAssignmentAggregate.transition(
        state, "completed", _actor("cognitive_plane"), "done", LATER)
    assert state["state"] == "completed"
