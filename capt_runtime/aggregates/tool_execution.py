"""Durable ToolExecution aggregate.

This state machine records broker facts only. It never invokes an adapter or
infers an external effect from intent alone.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from ..contracts import require
from ..errors import IllegalTransition

TERMINAL_STATES = frozenset({"completed", "failed", "cancelled", "indeterminate"})
TRANSITIONS = {
    "prepared": frozenset({"admitted", "failed", "cancelled"}),
    "admitted": frozenset({"dispatching", "failed", "cancelled"}),
    "dispatching": frozenset({"effect_observed", "settling", "failed", "cancelled", "indeterminate"}),
    "effect_observed": frozenset({"settling", "failed", "cancelled", "indeterminate"}),
    "settling": frozenset({"completed", "failed", "cancelled", "indeterminate"}),
    "completed": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
    "indeterminate": frozenset(),
}

_MUTABLE_FIELDS = frozenset({
    "reservationId", "dispatchBoundary", "result", "resultDigest", "sideEffectIdentity",
    "settlementStatus", "reconciliationReason", "updatedAt",
})


class ToolExecutionAggregate:
    KIND = "tool_execution"

    @staticmethod
    def stream_id(tool_execution_id: str) -> str:
        return "tool_execution-" + tool_execution_id

    @staticmethod
    def create(execution: Dict[str, Any]) -> Dict[str, Any]:
        require("ToolExecution", execution)
        if execution["state"] != "prepared":
            raise IllegalTransition(
                f"tool execution {execution['toolExecutionId']}", execution["state"], "prepared"
            )
        return deepcopy(execution)

    @staticmethod
    def transition(
        state: Dict[str, Any], to_state: str, patch: Dict[str, Any]
    ) -> Dict[str, Any]:
        require("ToolExecution", state)
        current = state["state"]
        if current in TERMINAL_STATES or to_state not in TRANSITIONS.get(current, frozenset()):
            raise IllegalTransition(
                f"tool execution {state['toolExecutionId']}", current, to_state
            )
        forbidden = set(patch) - _MUTABLE_FIELDS
        if forbidden:
            raise IllegalTransition(
                f"tool execution {state['toolExecutionId']} immutable fields {sorted(forbidden)!r}",
                current,
                to_state,
            )
        nxt = deepcopy(state)
        nxt.update(patch)
        nxt["state"] = to_state

        if to_state == "dispatching" and nxt["dispatchBoundary"] == "not_started":
            raise IllegalTransition(
                f"tool execution {state['toolExecutionId']} requires dispatch boundary",
                current,
                to_state,
            )
        if to_state == "settling" and nxt["settlementStatus"] != "settling":
            raise IllegalTransition(
                f"tool execution {state['toolExecutionId']} requires settling status",
                current,
                to_state,
            )
        if to_state in {"completed", "failed", "cancelled"}:
            if not nxt.get("result") or not nxt.get("resultDigest") or nxt["settlementStatus"] != "settled":
                raise IllegalTransition(
                    f"tool execution {state['toolExecutionId']} requires settled result",
                    current,
                    to_state,
                )
        if to_state == "indeterminate":
            if nxt["settlementStatus"] != "reconciliation_required" or not nxt.get("reconciliationReason"):
                raise IllegalTransition(
                    f"tool execution {state['toolExecutionId']} requires reconciliation reason",
                    current,
                    to_state,
                )
        require("ToolExecution", nxt)
        return nxt
