"""Governed Skill Workshop lifecycle state machine."""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from ..errors import AuthorityViolation, IllegalTransition

_TRANSITIONS = {
    "idea": {"draft", "rejected"},
    "draft": {"review", "rejected"},
    "review": {"sandbox", "rejected"},
    "sandbox": {"test", "rejected"},
    "test": {"red_team", "rejected"},
    "red_team": {"shadow", "rejected"},
    "shadow": {"approved", "rejected"},
    "approved": {"active", "rejected"},
    "active": {"revoked", "superseded"},
    "rejected": set(), "revoked": set(), "superseded": set(),
}
_FINAL_AUTHORITY_STATES = {"approved", "active", "revoked", "superseded"}


class SkillCandidateAggregate(object):
    KIND = "skill_candidate"
    OWNED_FIELDS = frozenset({
        "skill_candidate.name", "skill_candidate.sourceKind",
        "skill_candidate.lifecycleState", "skill_candidate.requiredAuthority",
        "skill_candidate.provenanceRefs", "skill_candidate.revision",
        "skill_candidate.createdBy", "skill_candidate.createdAt",
        "skill_candidate.decisionReason",
    })
    REFERENCE_FIELDS = frozenset({"skillId", "botId"})

    @staticmethod
    def stream_id(skill_id: str) -> str:
        if not skill_id:
            raise ValueError("SKILL_ID_REQUIRED")
        return "skill_candidate-" + skill_id

    @staticmethod
    def create(spec: Mapping[str, Any]) -> Dict[str, Any]:
        if spec.get("lifecycleState") != "idea":
            raise AuthorityViolation("SKILL_CANDIDATE_MUST_START_IDEA")
        if spec.get("decisionReason") is not None:
            raise AuthorityViolation("SKILL_CANDIDATE_CANNOT_SEED_DECISION")
        return {
            "skillId": str(spec["skillId"]), "botId": str(spec["botId"]),
            "name": str(spec["name"]), "sourceKind": str(spec["sourceKind"]),
            "lifecycleState": "idea",
            "requiredAuthority": list(spec.get("requiredAuthority") or []),
            "provenanceRefs": list(spec.get("provenanceRefs") or []),
            "revision": int(spec["revision"]), "createdBy": dict(spec["createdBy"]),
            "createdAt": str(spec["createdAt"]), "decisionReason": None,
        }

    @staticmethod
    def transition(
        current: Mapping[str, Any], to_state: str, actor: Mapping[str, Any],
        reason: Optional[str],
    ) -> Dict[str, Any]:
        prior = str(current["lifecycleState"])
        if to_state not in _TRANSITIONS.get(prior, set()):
            raise IllegalTransition("skill candidate %s" % current["skillId"], prior, to_state)
        if (prior in _FINAL_AUTHORITY_STATES or to_state in _FINAL_AUTHORITY_STATES) and actor.get("kind") not in {
            "human", "governance_kernel"
        }:
            raise AuthorityViolation("SKILL_FINAL_PROMOTION_REQUIRES_AUTHORITY")
        nxt = dict(current)
        nxt["lifecycleState"] = to_state
        nxt["decisionReason"] = reason
        return nxt
