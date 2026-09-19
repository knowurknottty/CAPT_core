"""Event-backed Lab Board work and human-blocker state machine."""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from ..errors import AuthorityViolation, IllegalTransition

_TRANSITIONS = {
    "inbox": {"ready", "human_task", "blocked_human", "done"},
    "ready": {"active", "waiting_agent", "waiting_human", "human_task", "blocked_human", "done"},
    "active": {"verifying", "waiting_agent", "waiting_human", "human_task", "blocked_human", "done"},
    "verifying": {"active", "waiting_agent", "waiting_human", "blocked_human", "done"},
    "waiting_agent": {"active", "ready", "blocked_human", "done"},
    "waiting_human": {"ready", "active", "human_task", "blocked_human", "done"},
    "human_task": {"ready", "active", "blocked_human", "done"},
    "blocked_human": {"ready", "active", "human_task", "done"},
    "done": set(),
}


class LabBoardAggregate(object):
    KIND = "lab_board"
    OWNED_FIELDS = frozenset({
        "lab_board.title", "lab_board.state", "lab_board.ownerRef",
        "lab_board.blockerReason", "lab_board.humanRequest",
        "lab_board.evidenceRefs", "lab_board.createdBy", "lab_board.createdAt",
        "lab_board.updatedAt",
    })
    REFERENCE_FIELDS = frozenset({"itemId", "missionId"})

    @staticmethod
    def stream_id(item_id: str) -> str:
        if not item_id:
            raise ValueError("LAB_BOARD_ITEM_ID_REQUIRED")
        return "lab_board-" + item_id

    @staticmethod
    def create(spec: Mapping[str, Any]) -> Dict[str, Any]:
        if spec.get("state") == "blocked_human" and not (
            spec.get("blockerReason") or spec.get("humanRequest")
        ):
            raise AuthorityViolation("HUMAN_BLOCKER_REASON_REQUIRED")
        return {
            "itemId": str(spec["itemId"]), "missionId": spec.get("missionId"),
            "title": str(spec["title"]), "state": str(spec["state"]),
            "ownerRef": spec.get("ownerRef"), "blockerReason": spec.get("blockerReason"),
            "humanRequest": spec.get("humanRequest"),
            "evidenceRefs": list(spec.get("evidenceRefs") or []),
            "createdBy": dict(spec["createdBy"]), "createdAt": str(spec["createdAt"]),
            "updatedAt": str(spec["updatedAt"]),
        }

    @staticmethod
    def transition(
        current: Mapping[str, Any], to_state: str, actor: Mapping[str, Any],
        reason: Optional[str], updated_at: str,
    ) -> Dict[str, Any]:
        prior = str(current["state"])
        if prior == "blocked_human" and actor.get("kind") != "human":
            raise AuthorityViolation("HUMAN_ONLY_BLOCKER")
        if to_state not in _TRANSITIONS.get(prior, set()):
            raise IllegalTransition("lab board item %s" % current["itemId"], prior, to_state)
        nxt = dict(current)
        nxt["state"] = to_state
        nxt["updatedAt"] = updated_at
        if to_state == "blocked_human" and reason:
            nxt["blockerReason"] = reason
        return nxt
