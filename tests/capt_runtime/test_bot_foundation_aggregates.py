from __future__ import annotations

import pytest

from capt_runtime.errors import AuthorityViolation


def _actor(kind="human"):
    return {"actorId": "a1", "kind": kind, "displayName": None}


def test_bot_delegate_requires_mission_binding():
    from capt_runtime.aggregates.bot import BotAggregate
    spec = {"botId": "worker", "displayName": "Worker", "roleKind": "delegate",
            "role": "research", "missionId": None, "modelStrategy": {},
            "cognitionPolicy": {}, "localityPolicy": {}, "collaboration": {},
            "authorityTemplateRef": None, "createdBy": _actor(), "createdAt": "2026-09-08T16:00:00Z"}
    with pytest.raises(AuthorityViolation, match="DELEGATE_MISSION_REQUIRED"):
        BotAggregate.create(spec)


def test_cognition_cannot_self_promote_even_autonomous_mode():
    from capt_runtime.aggregates.cognitive_candidate import CognitiveCandidateAggregate
    state = CognitiveCandidateAggregate.create({"candidateId": "cc1", "botId": "researcher",
        "kind": "hypothesis", "content": "x", "sourceRefs": [], "provenance": "event:1",
        "sensitivity": "project", "confidence": 0.8, "promotionMode": "autonomous",
        "state": "proposed", "proposedBy": _actor("cognitive_plane"),
        "proposedAt": "2026-09-08T16:00:00Z"})
    with pytest.raises(AuthorityViolation, match="COGNITION_SELF_PROMOTION_FORBIDDEN"):
        CognitiveCandidateAggregate.decide(state, "promote", _actor("cognitive_plane"),
                                           "2026-09-08T16:01:00Z", "looks good")


def test_locked_cognition_requires_human_but_governed_allows_governance():
    from capt_runtime.aggregates.cognitive_candidate import CognitiveCandidateAggregate
    base = {"candidateId": "cc2", "botId": "researcher", "kind": "preference", "content": "x",
        "sourceRefs": [], "provenance": "event:2", "sensitivity": "user", "confidence": 1.0,
        "state": "proposed", "proposedBy": _actor("cognitive_plane"), "proposedAt": "2026-09-08T16:00:00Z"}
    locked = CognitiveCandidateAggregate.create({**base, "promotionMode": "locked"})
    with pytest.raises(AuthorityViolation, match="LOCKED_COGNITION_REQUIRES_HUMAN"):
        CognitiveCandidateAggregate.decide(locked, "promote", _actor("governance_kernel"),
                                           "2026-09-08T16:01:00Z", None)
    governed = CognitiveCandidateAggregate.create({**base, "candidateId": "cc3", "promotionMode": "governed"})
    promoted = CognitiveCandidateAggregate.decide(governed, "promote", _actor("governance_kernel"),
                                                  "2026-09-08T16:01:00Z", None)
    assert promoted["state"] == "promoted"

def test_skill_activation_requires_human_or_governance():
    from capt_runtime.aggregates.skill_candidate import SkillCandidateAggregate
    state = SkillCandidateAggregate.create({"skillId": "sk1", "botId": "researcher",
        "name": "Research brief", "sourceKind": "demonstration", "lifecycleState": "idea",
        "requiredAuthority": [], "provenanceRefs": ["demo:1"], "revision": 1,
        "createdBy": _actor("cognitive_plane"), "createdAt": "2026-09-08T16:00:00Z"})
    for nxt in ["draft", "review", "sandbox", "test", "red_team", "shadow"]:
        state = SkillCandidateAggregate.transition(state, nxt, _actor("cognitive_plane"), None)
    with pytest.raises(AuthorityViolation, match="SKILL_FINAL_PROMOTION_REQUIRES_AUTHORITY"):
        SkillCandidateAggregate.transition(state, "approved", _actor("cognitive_plane"), None)
    state = SkillCandidateAggregate.transition(state, "approved", _actor("governance_kernel"), "verified")
    state = SkillCandidateAggregate.transition(state, "active", _actor("human"), "ship it")
    assert state["lifecycleState"] == "active"


def test_blocked_human_is_a_real_human_gate():
    from capt_runtime.aggregates.lab_board import LabBoardAggregate
    state = LabBoardAggregate.create({"itemId": "board1", "missionId": "m1", "title": "Need choice",
        "state": "blocked_human", "ownerRef": "researcher", "blockerReason": "two valid paths",
        "humanRequest": "choose A or B", "evidenceRefs": [], "createdBy": _actor("cognitive_plane"),
        "createdAt": "2026-09-08T16:00:00Z", "updatedAt": "2026-09-08T16:00:00Z"})
    with pytest.raises(AuthorityViolation, match="HUMAN_ONLY_BLOCKER"):
        LabBoardAggregate.transition(state, "ready", _actor("system"), "auto unblock", "2026-09-08T16:01:00Z")
    state = LabBoardAggregate.transition(state, "ready", _actor("human"), "decision made", "2026-09-08T16:01:00Z")
    assert state["state"] == "ready"


def test_new_aggregate_ownership_is_disjoint():
    from capt_runtime.aggregates import ALL_AGGREGATES
    seen = {}
    for aggregate in ALL_AGGREGATES:
        for field in aggregate.OWNED_FIELDS:
            seen.setdefault(field, []).append(aggregate.KIND)
    assert {field: owners for field, owners in seen.items() if len(owners) > 1} == {}

def test_cognition_cannot_reverse_an_authorized_skill_decision():
    from capt_runtime.aggregates.skill_candidate import SkillCandidateAggregate
    state = SkillCandidateAggregate.create({"skillId": "sk2", "botId": "researcher",
        "name": "Verified skill", "sourceKind": "experience", "lifecycleState": "idea",
        "requiredAuthority": [], "provenanceRefs": ["experience:1"], "revision": 1,
        "createdBy": _actor("cognitive_plane"), "createdAt": "2026-09-08T16:00:00Z"})
    for nxt in ["draft", "review", "sandbox", "test", "red_team", "shadow"]:
        state = SkillCandidateAggregate.transition(state, nxt, _actor("cognitive_plane"), None)
    state = SkillCandidateAggregate.transition(state, "approved", _actor("governance_kernel"), "verified")
    with pytest.raises(AuthorityViolation, match="SKILL_FINAL_PROMOTION_REQUIRES_AUTHORITY"):
        SkillCandidateAggregate.transition(state, "rejected", _actor("cognitive_plane"), "changed my mind")


def test_cognitive_candidate_cannot_seed_decision_metadata():
    from capt_runtime.aggregates.cognitive_candidate import CognitiveCandidateAggregate
    spec = {"candidateId": "cc-seeded", "botId": "researcher", "kind": "hypothesis",
        "content": "candidate", "sourceRefs": ["event:1"], "provenance": "event:1",
        "sensitivity": "project", "confidence": 0.5, "promotionMode": "governed",
        "state": "proposed", "proposedBy": _actor("cognitive_plane"),
        "proposedAt": "2026-09-08T16:00:00Z", "decidedBy": _actor("human"),
        "decidedAt": "2026-09-08T16:00:01Z", "decisionReason": "pre-approved"}
    with pytest.raises(AuthorityViolation, match="COGNITIVE_CANDIDATE_CANNOT_SEED_DECISION"):
        CognitiveCandidateAggregate.create(spec)


def test_skill_candidate_cannot_seed_decision_reason():
    from capt_runtime.aggregates.skill_candidate import SkillCandidateAggregate
    spec = {"skillId": "sk-seeded", "botId": "researcher", "name": "Seeded skill",
        "sourceKind": "experience", "lifecycleState": "idea", "requiredAuthority": [],
        "provenanceRefs": ["experience:1"], "revision": 1,
        "createdBy": _actor("cognitive_plane"), "createdAt": "2026-09-08T16:00:00Z",
        "decisionReason": "already approved"}
    with pytest.raises(AuthorityViolation, match="SKILL_CANDIDATE_CANNOT_SEED_DECISION"):
        SkillCandidateAggregate.create(spec)
