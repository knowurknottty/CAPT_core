"""Pure EventStore projection for CAPT Lab standups."""
from __future__ import annotations

from typing import Any, Dict, List

from .aggregates.bot import BotAggregate
from .aggregates.delegate_assignment import DelegateAssignmentAggregate
from .aggregates.lab_board import LabBoardAggregate
from .store import EventStore


def _states_of_kind(store: EventStore, kind: str) -> List[Dict[str, Any]]:
    rows = []
    for stream_id, aggregate_kind, _version in store.all_aggregates():
        if aggregate_kind != kind:
            continue
        state = store.load_state(stream_id)
        if state is not None:
            rows.append(dict(state))
    return rows


def build_lab_standup(store: EventStore, now: str) -> Dict[str, Any]:
    """Build a deterministic read-only standup projection from durable state."""
    bots = _states_of_kind(store, BotAggregate.KIND)
    assignments = _states_of_kind(store, DelegateAssignmentAggregate.KIND)
    board = _states_of_kind(store, LabBoardAggregate.KIND)

    crew = sorted(
        (bot for bot in bots if bot.get("roleKind") == "crew"),
        key=lambda bot: (str(bot.get("displayName") or ""), str(bot["botId"])),
    )
    active_delegates = sorted(
        (
            assignment for assignment in assignments
            if assignment.get("state") == "active" and str(assignment.get("expiresAt")) > now
        ),
        key=lambda assignment: str(assignment["assignmentId"]),
    )
    by_state = {}
    for item in board:
        by_state.setdefault(str(item["state"]), []).append(item)
    for items in by_state.values():
        items.sort(key=lambda item: (str(item.get("updatedAt") or ""), str(item["itemId"])))

    return {
        "generatedAt": now,
        "crew": crew,
        "activeDelegates": active_delegates,
        "humanTasks": by_state.get("human_task", []),
        "humanRequests": by_state.get("waiting_human", []),
        "humanBlockers": by_state.get("blocked_human", []),
        "ready": by_state.get("ready", []),
        "active": by_state.get("active", []),
        "verifying": by_state.get("verifying", []),
        "waitingAgent": by_state.get("waiting_agent", []),
        "done": by_state.get("done", []),
    }
