"""Mission-scoped delegation coordination without capability authority."""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from ..errors import AuthorityViolation, IllegalTransition

_TERMINAL = {"completed", "revoked", "expired"}
_TRANSITIONS = {"active": _TERMINAL, "completed": set(), "revoked": set(), "expired": set()}


class DelegateAssignmentAggregate(object):
    KIND = "delegate_assignment"
    OWNED_FIELDS = frozenset({
        "delegate_assignment.parentBotId", "delegate_assignment.delegateBotId",
        "delegate_assignment.missionId", "delegate_assignment.taskId",
        "delegate_assignment.depth", "delegate_assignment.state",
        "delegate_assignment.createdAt", "delegate_assignment.expiresAt",
        "delegate_assignment.createdBy", "delegate_assignment.lastTransitionAt",
        "delegate_assignment.transitionReason",
    })
    REFERENCE_FIELDS = frozenset({"assignmentId"})

    @staticmethod
    def stream_id(assignment_id: str) -> str:
        if not assignment_id:
            raise ValueError("DELEGATE_ASSIGNMENT_ID_REQUIRED")
        return "delegate_assignment-" + assignment_id
    @staticmethod
    def create(spec: Mapping[str, Any]) -> Dict[str, Any]:
        if spec.get("state") != "active":
            raise AuthorityViolation("DELEGATE_ASSIGNMENT_MUST_START_ACTIVE")
        if str(spec["expiresAt"]) <= str(spec["createdAt"]):
            raise AuthorityViolation("DELEGATE_EXPIRY_NOT_AFTER_CREATION")
        return {
            "assignmentId": str(spec["assignmentId"]),
            "parentBotId": str(spec["parentBotId"]),
            "delegateBotId": str(spec["delegateBotId"]),
            "missionId": str(spec["missionId"]), "taskId": spec.get("taskId"),
            "depth": int(spec["depth"]), "state": "active",
            "createdAt": str(spec["createdAt"]), "expiresAt": str(spec["expiresAt"]),
            "createdBy": dict(spec["createdBy"]),
            "lastTransitionAt": str(spec["lastTransitionAt"]),
            "transitionReason": spec.get("transitionReason"),
        }

    @staticmethod
    def transition(
        current: Mapping[str, Any], to_state: str, actor: Mapping[str, Any],
        reason: Optional[str], at: str,
    ) -> Dict[str, Any]:
        prior = str(current["state"])
        if to_state not in _TRANSITIONS.get(prior, set()):
            raise IllegalTransition("delegate assignment %s" % current["assignmentId"], prior, to_state)
        actor_kind = str(actor.get("kind") or "")
        if to_state == "revoked" and actor_kind not in {"human", "governance_kernel", "system"}:
            raise AuthorityViolation("DELEGATE_REVOCATION_REQUIRES_AUTHORITY")
        if to_state == "expired" and actor_kind not in {"governance_kernel", "system"}:
            raise AuthorityViolation("DELEGATE_EXPIRY_REQUIRES_SYSTEM")
        nxt = dict(current)
        nxt["state"] = to_state
        nxt["lastTransitionAt"] = at
        nxt["transitionReason"] = reason
        return nxt
