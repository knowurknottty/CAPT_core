"""Governed persistent-cognition candidate state machine."""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from ..errors import AuthorityViolation, IllegalTransition


class CognitiveCandidateAggregate(object):
    KIND = "cognitive_candidate"
    OWNED_FIELDS = frozenset({
        "cognitive_candidate.kind", "cognitive_candidate.content",
        "cognitive_candidate.sourceRefs", "cognitive_candidate.provenance",
        "cognitive_candidate.sensitivity", "cognitive_candidate.confidence",
        "cognitive_candidate.promotionMode", "cognitive_candidate.state",
        "cognitive_candidate.proposedBy", "cognitive_candidate.proposedAt",
        "cognitive_candidate.decidedBy", "cognitive_candidate.decidedAt",
        "cognitive_candidate.decisionReason",
    })
    REFERENCE_FIELDS = frozenset({"candidateId", "botId"})

    @staticmethod
    def stream_id(candidate_id: str) -> str:
        if not candidate_id:
            raise ValueError("COGNITIVE_CANDIDATE_ID_REQUIRED")
        return "cognitive_candidate-" + candidate_id

    @staticmethod
    def create(spec: Mapping[str, Any]) -> Dict[str, Any]:
        if spec.get("state") != "proposed":
            raise AuthorityViolation("COGNITIVE_CANDIDATE_MUST_START_PROPOSED")
        if any(spec.get(field) is not None for field in ("decidedBy", "decidedAt", "decisionReason")):
            raise AuthorityViolation("COGNITIVE_CANDIDATE_CANNOT_SEED_DECISION")
        return {
            "candidateId": str(spec["candidateId"]), "botId": str(spec["botId"]),
            "kind": str(spec["kind"]), "content": str(spec["content"]),
            "sourceRefs": list(spec.get("sourceRefs") or []),
            "provenance": str(spec["provenance"]), "sensitivity": str(spec["sensitivity"]),
            "confidence": float(spec["confidence"]), "promotionMode": str(spec["promotionMode"]),
            "state": "proposed", "proposedBy": dict(spec["proposedBy"]),
            "proposedAt": str(spec["proposedAt"]), "decidedBy": None,
            "decidedAt": None, "decisionReason": None,
        }

    @staticmethod
    def decide(
        current: Mapping[str, Any], decision: str, actor: Mapping[str, Any],
        decided_at: str, reason: Optional[str],
    ) -> Dict[str, Any]:
        actor_kind = str(actor.get("kind") or "")
        if actor_kind == "cognitive_plane":
            raise AuthorityViolation("COGNITION_SELF_PROMOTION_FORBIDDEN")
        if actor_kind not in {"human", "governance_kernel"}:
            raise AuthorityViolation("COGNITIVE_DECISION_REQUIRES_AUTHORITY")
        if current["promotionMode"] == "locked" and actor_kind != "human":
            raise AuthorityViolation("LOCKED_COGNITION_REQUIRES_HUMAN")

        target = {"promote": "promoted", "reject": "rejected", "revoke": "revoked"}.get(decision)
        if target is None:
            raise AuthorityViolation("COGNITIVE_DECISION_INVALID")
        allowed = {
            "proposed": {"promoted", "rejected"},
            "promoted": {"revoked"},
            "rejected": set(),
            "revoked": set(),
        }
        prior = str(current["state"])
        if target not in allowed.get(prior, set()):
            raise IllegalTransition("cognitive candidate %s" % current["candidateId"], prior, target)
        nxt = dict(current)
        nxt["state"] = target
        nxt["decidedBy"] = dict(actor)
        nxt["decidedAt"] = decided_at
        nxt["decisionReason"] = reason
        return nxt
