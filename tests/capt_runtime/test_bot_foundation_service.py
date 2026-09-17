from __future__ import annotations

import pytest

from capt_runtime import commands
from capt_runtime.errors import AuthorityViolation
from capt_runtime.governed_service import GovernedRuntimeService
from capt_runtime.store import EventStore

NOW = "2026-09-08T16:00:00Z"


def _actor(kind="human", actor_id="captain"):
    return {"actorId": actor_id, "kind": kind, "displayName": None}


def _meta(name, actor_kind="human", subject=None):
    subject = subject or {"name": name}
    return commands.command(
        command_id="cmd-" + name, idempotency_key="idem-" + name,
        operation_fingerprint=commands.fingerprint(name, subject),
        correlation_id="corr-bot-r1", actor_id="actor-" + actor_kind,
        actor_kind=actor_kind, issued_at=NOW,
    )


def _bot():
    return {"schemaVersion": "1.0.0", "botId": "researcher", "displayName": "Researcher",
        "roleKind": "crew", "role": "research", "missionId": None,
        "modelStrategy": {"primary": None, "fallbacks": []},
        "cognitionPolicy": {"promotionMode": "governed"},
        "localityPolicy": {"defaultRuntime": "local", "privateData": "local_only"},
        "collaboration": {"mayDelegate": True, "maxSpawnDepth": 2},
        "authorityTemplateRef": None, "createdBy": _actor(), "createdAt": NOW}


def _register_default_bot(service, suffix):
    service.register_bot(_bot(), _meta("register-bot-" + suffix))


def test_bot_registration_is_durable_and_idempotent():
    store = EventStore(":memory:")
    service = GovernedRuntimeService(store)
    meta = _meta("register-bot")
    first = service.register_bot(_bot(), meta)
    second = service.register_bot(_bot(), meta)
    assert first["bot"]["botId"] == "researcher"
    assert second["status"] == "idempotent"
    assert store.aggregate_version("bot-researcher") == 1
    assert [e["eventType"] for e in store.read_stream("bot-researcher")] == ["BotRegistered"]

def _candidate(candidate_id="cc1", mode="governed"):
    return {"schemaVersion": "1.0.0", "candidateId": candidate_id, "botId": "researcher",
        "kind": "hypothesis", "content": "public research benefits from cloud fan-out",
        "sourceRefs": ["event:1"], "provenance": "ledger:event:1", "sensitivity": "project",
        "confidence": 0.8, "promotionMode": mode, "state": "proposed",
        "proposedBy": _actor("cognitive_plane", "researcher"), "proposedAt": NOW,
        "decidedBy": None, "decidedAt": None, "decisionReason": None}


def test_cognitive_candidate_persists_but_cognition_cannot_decide_it():
    store = EventStore(":memory:")
    service = GovernedRuntimeService(store)
    _register_default_bot(service, "cognition")
    service.propose_cognitive_candidate(_candidate(), _meta("propose-cc", "cognitive_plane"))
    with pytest.raises(AuthorityViolation):
        service.decide_cognitive_candidate("cc1", "promote", "self approve",
                                           _meta("decide-cc-bad", "cognitive_plane"))
    result = service.decide_cognitive_candidate("cc1", "promote", "policy permits",
                                                _meta("decide-cc", "governance_kernel"))
    assert result["candidate"]["state"] == "promoted"
    assert store.aggregate_version("cognitive_candidate-cc1") == 2


def _skill():
    return {"schemaVersion": "1.0.0", "skillId": "sk1", "botId": "researcher",
        "name": "Research brief", "sourceKind": "demonstration", "lifecycleState": "idea",
        "requiredAuthority": [], "provenanceRefs": ["demo:1"], "revision": 1,
        "createdBy": _actor("cognitive_plane", "researcher"), "createdAt": NOW,
        "decisionReason": None}


def test_skill_workshop_final_promotion_is_not_cognitive_authority():
    store = EventStore(":memory:")
    service = GovernedRuntimeService(store)
    _register_default_bot(service, "skill")
    service.create_skill_candidate(_skill(), _meta("create-skill", "cognitive_plane"))
    for i, state in enumerate(["draft", "review", "sandbox", "test", "red_team", "shadow"]):
        service.transition_skill_candidate("sk1", state, None,
            _meta("skill-step-%d" % i, "cognitive_plane", {"to": state}))
    with pytest.raises(AuthorityViolation):
        service.transition_skill_candidate("sk1", "approved", "self approve",
            _meta("skill-approve-bad", "cognitive_plane"))
    result = service.transition_skill_candidate("sk1", "approved", "verified",
        _meta("skill-approve", "governance_kernel"))
    assert result["candidate"]["lifecycleState"] == "approved"

def _board_item():
    return {"schemaVersion": "1.0.0", "itemId": "board1", "missionId": None,
        "title": "Choose architecture", "state": "blocked_human", "ownerRef": "researcher",
        "blockerReason": "two valid paths", "humanRequest": "Captain choose A or B",
        "evidenceRefs": ["evidence:1"], "createdBy": _actor("cognitive_plane", "researcher"),
        "createdAt": NOW, "updatedAt": NOW}


def test_lab_board_human_blocker_survives_service_boundary():
    store = EventStore(":memory:")
    service = GovernedRuntimeService(store)
    service.create_lab_board_item(_board_item(), _meta("board-create", "cognitive_plane"))
    with pytest.raises(AuthorityViolation, match="HUMAN_ONLY_BLOCKER"):
        service.transition_lab_board_item("board1", "ready", "auto resolved",
                                          _meta("board-auto", "system"))
    result = service.transition_lab_board_item("board1", "ready", "Captain chose A",
                                               _meta("board-human", "human"))
    assert result["item"]["state"] == "ready"
    assert store.aggregate_version("lab_board-board1") == 2


def test_bot_stream_does_not_contain_authority_or_secrets():
    store = EventStore(":memory:")
    service = GovernedRuntimeService(store)
    service.register_bot(_bot(), _meta("register-bot-separation"))
    state = store.require_state("bot-researcher")
    forbidden = {"apiKey", "credentials", "grants", "leases", "capabilities"}
    assert forbidden.isdisjoint(state)


def test_bot_foundation_streams_replay_to_authoritative_state():
    from capt_runtime.replay import full_replay

    store = EventStore(":memory:")
    service = GovernedRuntimeService(store)
    service.register_bot(_bot(), _meta("replay-bot"))
    service.propose_cognitive_candidate(_candidate("cc-replay"),
                                        _meta("replay-cc", "cognitive_plane"))
    service.decide_cognitive_candidate("cc-replay", "promote", "verified",
                                       _meta("replay-cc-decide", "governance_kernel"))
    service.create_skill_candidate({**_skill(), "skillId": "sk-replay"},
                                   _meta("replay-skill", "cognitive_plane"))
    service.transition_skill_candidate("sk-replay", "draft", None,
                                       _meta("replay-skill-draft", "cognitive_plane"))
    service.create_lab_board_item({**_board_item(), "itemId": "board-replay"},
                                  _meta("replay-board", "cognitive_plane"))
    service.transition_lab_board_item("board-replay", "ready", "human decision",
                                      _meta("replay-board-ready", "human"))

    replayed = full_replay(store)
    for stream in ["bot-researcher", "cognitive_candidate-cc-replay",
                   "skill_candidate-sk-replay", "lab_board-board-replay"]:
        assert replayed.aggregates[stream] == store.require_state(stream)


def test_delegate_registration_requires_existing_mission():
    store = EventStore(":memory:")
    service = GovernedRuntimeService(store)
    delegate = {**_bot(), "botId": "delegate1", "displayName": "Delegate 1",
                "roleKind": "delegate", "missionId": "missing-mission"}
    with pytest.raises(AuthorityViolation, match="DELEGATE_MISSION_NOT_FOUND"):
        service.register_bot(delegate, _meta("register-missing-delegate"))


def test_delegate_registration_accepts_existing_durable_mission():
    store = EventStore(":memory:")
    service = GovernedRuntimeService(store)
    mission = {
        "schemaVersion": "1.0.0", "missionId": "m-delegate", "rawRequest": "delegate work",
        "normalizedRequest": "delegate work",
        "objectives": [{"objectiveId": "obj-1", "statement": "bounded delegate work", "priority": 1}],
        "constraints": [],
        "successCriteria": [{"criterionId": "sc-1", "statement": "work complete", "requiresVerification": True}],
        "terminationCriteria": [{"criterionId": "tc-1", "statement": "stop on failure", "terminalState": "failed"}],
        "unresolvedAmbiguities": [], "taskGraphId": None, "createdAt": NOW,
    }
    service.create_mission(mission, _meta("create-delegate-mission"))
    delegate = {**_bot(), "botId": "delegate-ok", "displayName": "Delegate OK",
                "roleKind": "delegate", "missionId": "m-delegate"}
    result = service.register_bot(delegate, _meta("register-delegate-ok"))
    assert result["bot"]["missionId"] == "m-delegate"
    assert store.aggregate_version("bot-delegate-ok") == 1


def test_cognitive_candidate_requires_registered_bot():
    store = EventStore(":memory:")
    service = GovernedRuntimeService(store)
    candidate = {**_candidate("cc-orphan"), "botId": "missing-bot"}
    with pytest.raises(AuthorityViolation, match="COGNITIVE_CANDIDATE_BOT_NOT_FOUND"):
        service.propose_cognitive_candidate(candidate, _meta("orphan-cognition", "cognitive_plane"))


def test_cognitive_candidate_cannot_override_bot_promotion_policy():
    store = EventStore(":memory:")
    service = GovernedRuntimeService(store)
    locked_bot = {**_bot(), "cognitionPolicy": {"promotionMode": "locked"}}
    service.register_bot(locked_bot, _meta("register-locked-bot"))
    candidate = _candidate("cc-mode-mismatch", mode="governed")
    with pytest.raises(AuthorityViolation, match="COGNITIVE_PROMOTION_MODE_MISMATCH"):
        service.propose_cognitive_candidate(candidate, _meta("mode-mismatch", "cognitive_plane"))


def test_skill_candidate_requires_registered_bot():
    store = EventStore(":memory:")
    service = GovernedRuntimeService(store)
    candidate = {**_skill(), "skillId": "sk-orphan", "botId": "missing-bot"}
    with pytest.raises(AuthorityViolation, match="SKILL_CANDIDATE_BOT_NOT_FOUND"):
        service.create_skill_candidate(candidate, _meta("orphan-skill", "cognitive_plane"))


def test_lab_board_mission_reference_must_exist_when_present():
    store = EventStore(":memory:")
    service = GovernedRuntimeService(store)
    item = {**_board_item(), "itemId": "board-orphan", "missionId": "missing-mission"}
    with pytest.raises(AuthorityViolation, match="LAB_BOARD_MISSION_NOT_FOUND"):
        service.create_lab_board_item(item, _meta("orphan-board", "cognitive_plane"))
