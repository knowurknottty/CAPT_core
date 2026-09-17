from __future__ import annotations

import pytest

from capt_runtime import commands
from capt_runtime.errors import AuthorityViolation
from capt_runtime.governed_service import GovernedRuntimeService
from capt_runtime.store import EventStore

NOW = "2026-09-08T17:00:00Z"
LATER = "2026-09-08T18:00:00Z"


def _meta(name, kind="human"):
    return commands.command(
        command_id="cmd-" + name, idempotency_key="idem-" + name,
        operation_fingerprint=commands.fingerprint(name, {"name": name}),
        correlation_id="corr-r2", actor_id="researcher" if kind == "cognitive_plane" else "actor-" + kind,
        actor_kind=kind, issued_at=NOW,
    )


def _bot(bot_id, role_kind, mission_id=None, may_delegate=True, max_depth=2):
    return {"schemaVersion": "1.0.0", "botId": bot_id, "displayName": bot_id,
        "roleKind": role_kind, "role": "worker", "missionId": mission_id,
        "modelStrategy": {"primary": None, "fallbacks": []},
        "cognitionPolicy": {"promotionMode": "governed"},
        "localityPolicy": {"defaultRuntime": "local", "privateData": "local_only"},
        "collaboration": {"mayDelegate": may_delegate, "maxSpawnDepth": max_depth},
        "authorityTemplateRef": None,
        "createdBy": {"actorId": "captain", "kind": "human", "displayName": None},
        "createdAt": NOW}


def _mission(mission_id="m1"):
    return {"schemaVersion": "1.0.0", "missionId": mission_id,
        "rawRequest": "delegated work", "normalizedRequest": "delegated work",
        "objectives": [{"objectiveId": "obj-1", "statement": "bounded work", "priority": 1}],
        "constraints": [],
        "successCriteria": [{"criterionId": "sc-1", "statement": "done", "requiresVerification": True}],
        "terminationCriteria": [{"criterionId": "tc-1", "statement": "stop", "terminalState": "failed"}],
        "unresolvedAmbiguities": [], "taskGraphId": None, "createdAt": NOW}


def _assignment(**overrides):
    value = {"schemaVersion": "1.0.0", "assignmentId": "da-1",
        "parentBotId": "researcher", "delegateBotId": "delegate-1",
        "missionId": "m1", "taskId": None, "depth": 1, "state": "active",
        "createdAt": NOW, "expiresAt": LATER,
        "createdBy": {"actorId": "researcher", "kind": "cognitive_plane", "displayName": None},
        "lastTransitionAt": NOW, "transitionReason": None}
    value.update(overrides)
    return value


def _setup():
    store = EventStore(":memory:")
    service = GovernedRuntimeService(store)
    service.create_mission(_mission(), _meta("mission"))
    service.register_bot(_bot("researcher", "crew"), _meta("parent"))
    service.register_bot(_bot("delegate-1", "delegate", "m1"), _meta("delegate"))
    return store, service


def test_assignment_is_durable_and_creates_no_capability_state():
    store, service = _setup()
    result = service.assign_delegate(_assignment(), _meta("assign", "cognitive_plane"))
    assert result["assignment"]["state"] == "active"
    assert store.aggregate_version("delegate_assignment-da-1") == 1
    assert not any(sid.startswith("capability-") for sid, _kind, _ver in store.all_aggregates())


def test_assignment_requires_matching_delegate_mission_and_depth():
    _store, service = _setup()
    with pytest.raises(AuthorityViolation, match="DELEGATE_ASSIGNMENT_MISSION_MISMATCH"):
        service.assign_delegate(_assignment(missionId="other"), _meta("assign-bad-mission", "cognitive_plane"))
    with pytest.raises(AuthorityViolation, match="DELEGATE_DEPTH_INVALID"):
        service.assign_delegate(_assignment(depth=2), _meta("assign-bad-depth", "cognitive_plane"))


def test_assignment_respects_parent_delegation_policy():
    store = EventStore(":memory:")
    service = GovernedRuntimeService(store)
    service.create_mission(_mission(), _meta("mission-no-delegate"))
    service.register_bot(_bot("researcher", "crew", may_delegate=False), _meta("parent-no-delegate"))
    service.register_bot(_bot("delegate-1", "delegate", "m1"), _meta("delegate-no-delegate"))
    with pytest.raises(AuthorityViolation, match="PARENT_DELEGATION_FORBIDDEN"):
        service.assign_delegate(_assignment(), _meta("assign-forbidden", "cognitive_plane"))


def test_assignment_transition_is_durable_and_terminal():
    store, service = _setup()
    service.assign_delegate(_assignment(), _meta("assign-transition", "cognitive_plane"))
    result = service.transition_delegate_assignment(
        "da-1", "completed", "work returned", _meta("complete", "system"))
    assert result["assignment"]["state"] == "completed"
    assert store.aggregate_version("delegate_assignment-da-1") == 2


def test_nested_delegate_requires_active_parent_chain_and_ancestor_depth_limit():
    store, service = _setup()
    service.register_bot(_bot("delegate-2", "delegate", "m1", max_depth=8),
                         _meta("delegate-2"))
    service.assign_delegate(_assignment(), _meta("assign-parent", "cognitive_plane"))
    nested = _assignment(assignmentId="da-2", parentBotId="delegate-1",
                         delegateBotId="delegate-2", depth=2)
    result = service.assign_delegate(nested, _meta("assign-nested", "cognitive_plane"))
    assert result["assignment"]["depth"] == 2

    limited_store = EventStore(":memory:")
    limited = GovernedRuntimeService(limited_store)
    limited.create_mission(_mission(), _meta("mission-limited"))
    limited.register_bot(_bot("researcher", "crew", max_depth=1), _meta("parent-limited"))
    limited.register_bot(_bot("delegate-1", "delegate", "m1", max_depth=8), _meta("d1-limited"))
    limited.register_bot(_bot("delegate-2", "delegate", "m1", max_depth=8), _meta("d2-limited"))
    limited.assign_delegate(_assignment(), _meta("assign-limited-parent", "cognitive_plane"))
    with pytest.raises(AuthorityViolation, match="DELEGATE_DEPTH_INVALID"):
        limited.assign_delegate(nested, _meta("assign-limited-child", "cognitive_plane"))


def test_assignment_creation_metadata_is_bound_to_command():
    _store, service = _setup()
    forged = _assignment(createdAt="2026-09-08T16:00:00Z")
    with pytest.raises(AuthorityViolation, match="DELEGATE_ASSIGNMENT_METADATA_MISMATCH"):
        service.assign_delegate(forged, _meta("assign-forged", "cognitive_plane"))


def test_expired_assignment_cannot_complete_after_expiry():
    _store, service = _setup()
    service.assign_delegate(_assignment(), _meta("assign-expiry", "cognitive_plane"))
    late = commands.command(
        command_id="cmd-late", idempotency_key="idem-late",
        operation_fingerprint=commands.fingerprint("late", {"assignmentId": "da-1"}),
        correlation_id="corr-r2", actor_id="researcher", actor_kind="cognitive_plane",
        issued_at="2026-09-08T19:00:00Z",
    )
    with pytest.raises(AuthorityViolation, match="DELEGATE_ASSIGNMENT_EXPIRED"):
        service.transition_delegate_assignment("da-1", "completed", "late", late)


def test_delegate_assignment_replays_to_authoritative_state():
    from capt_runtime.replay import full_replay

    store, service = _setup()
    service.assign_delegate(_assignment(), _meta("assign-replay", "cognitive_plane"))
    service.transition_delegate_assignment(
        "da-1", "completed", "returned", _meta("complete-replay", "system"))
    replayed = full_replay(store)
    assert replayed.aggregates["delegate_assignment-da-1"] == store.require_state(
        "delegate_assignment-da-1"
    )
