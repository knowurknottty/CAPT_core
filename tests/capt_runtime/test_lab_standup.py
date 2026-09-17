from __future__ import annotations

from capt_runtime import commands
from capt_runtime.governed_service import GovernedRuntimeService
from capt_runtime.store import EventStore

NOW = "2026-09-08T17:00:00Z"
LATER = "2026-09-08T18:00:00Z"


def _meta(name, kind="human"):
    return commands.command(
        command_id="cmd-" + name, idempotency_key="idem-" + name,
        operation_fingerprint=commands.fingerprint(name, {"name": name}),
        correlation_id="corr-standup", actor_id="researcher" if kind == "cognitive_plane" else "actor-" + kind,
        actor_kind=kind, issued_at=NOW,
    )


def _bot(bot_id, role_kind="crew", mission_id=None):
    return {"schemaVersion": "1.0.0", "botId": bot_id, "displayName": bot_id.title(),
        "roleKind": role_kind, "role": "worker", "missionId": mission_id,
        "modelStrategy": {"primary": None, "fallbacks": []},
        "cognitionPolicy": {"promotionMode": "governed"},
        "localityPolicy": {"defaultRuntime": "local", "privateData": "local_only"},
        "collaboration": {"mayDelegate": True, "maxSpawnDepth": 2},
        "authorityTemplateRef": None,
        "createdBy": {"actorId": "captain", "kind": "human", "displayName": None},
        "createdAt": NOW}


def _mission():
    return {"schemaVersion": "1.0.0", "missionId": "m1", "rawRequest": "standup",
        "normalizedRequest": "standup",
        "objectives": [{"objectiveId": "obj-1", "statement": "work", "priority": 1}],
        "constraints": [],
        "successCriteria": [{"criterionId": "sc-1", "statement": "done", "requiresVerification": True}],
        "terminationCriteria": [{"criterionId": "tc-1", "statement": "stop", "terminalState": "failed"}],
        "unresolvedAmbiguities": [], "taskGraphId": None, "createdAt": NOW}


def _board(item_id, state, title):
    return {"schemaVersion": "1.0.0", "itemId": item_id, "missionId": None,
        "title": title, "state": state, "ownerRef": "researcher",
        "blockerReason": "needs Captain" if state == "blocked_human" else None,
        "humanRequest": "choose" if state in {"blocked_human", "waiting_human", "human_task"} else None,
        "evidenceRefs": [],
        "createdBy": {"actorId": "researcher", "kind": "cognitive_plane", "displayName": None},
        "createdAt": NOW, "updatedAt": NOW}


def _assignment():
    return {"schemaVersion": "1.0.0", "assignmentId": "da-standup",
        "parentBotId": "researcher", "delegateBotId": "delegate-1", "missionId": "m1",
        "taskId": None, "depth": 1, "state": "active", "createdAt": NOW,
        "expiresAt": LATER, "createdBy": {"actorId": "researcher", "kind": "cognitive_plane", "displayName": None},
        "lastTransitionAt": NOW, "transitionReason": None}


def test_standup_is_pure_read_model_and_groups_human_attention():
    from capt_runtime.lab_standup import build_lab_standup

    store = EventStore(":memory:")
    service = GovernedRuntimeService(store)
    service.create_mission(_mission(), _meta("mission"))
    service.register_bot(_bot("researcher"), _meta("bot-researcher"))
    service.register_bot(_bot("verifier"), _meta("bot-verifier"))
    service.register_bot(_bot("delegate-1", "delegate", "m1"), _meta("bot-delegate"))
    service.assign_delegate(_assignment(), _meta("assignment", "cognitive_plane"))
    service.create_lab_board_item(_board("human-task", "human_task", "Review skill"), _meta("human-task", "cognitive_plane"))
    service.create_lab_board_item(_board("human-request", "waiting_human", "Choose model"), _meta("human-request", "cognitive_plane"))
    service.create_lab_board_item(_board("blocked", "blocked_human", "Approve credential"), _meta("blocked", "cognitive_plane"))
    service.create_lab_board_item(_board("active", "active", "Research competitors"), _meta("active", "cognitive_plane"))

    before_head = store.head_sequence()
    before_aggregates = list(store.all_aggregates())
    standup = build_lab_standup(store, NOW)
    assert store.head_sequence() == before_head
    assert list(store.all_aggregates()) == before_aggregates
    assert [bot["botId"] for bot in standup["crew"]] == ["researcher", "verifier"]
    assert [a["delegateBotId"] for a in standup["activeDelegates"]] == ["delegate-1"]
    assert [x["itemId"] for x in standup["humanTasks"]] == ["human-task"]
    assert [x["itemId"] for x in standup["humanRequests"]] == ["human-request"]
    assert [x["itemId"] for x in standup["humanBlockers"]] == ["blocked"]
    assert [x["itemId"] for x in standup["active"]] == ["active"]


def test_standup_excludes_expired_active_assignment():
    from capt_runtime.lab_standup import build_lab_standup

    store = EventStore(":memory:")
    service = GovernedRuntimeService(store)
    service.create_mission(_mission(), _meta("mission-expired"))
    service.register_bot(_bot("researcher"), _meta("bot-researcher-expired"))
    service.register_bot(_bot("delegate-1", "delegate", "m1"), _meta("bot-delegate-expired"))
    service.assign_delegate(_assignment(), _meta("assignment-expired", "cognitive_plane"))

    standup = build_lab_standup(store, "2026-09-08T19:00:00Z")
    assert standup["activeDelegates"] == []
