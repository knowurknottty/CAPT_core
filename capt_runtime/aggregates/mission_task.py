"""Aggregate state machines with exclusive ownership (ADR-0103).

Each aggregate owns a disjoint slice of runtime state and is the ONLY writer
of that slice. Ownership is declared in OWNED_FIELDS and asserted by the
conformance suite, so an overlap becomes a test failure rather than a subtle
correctness bug.

Aggregates are pure: they validate a transition and return the next state.
They never touch the database. Persistence belongs to EventStore; sequencing
belongs to the application services.
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, Optional

from ..errors import IllegalTransition

# ---------------------------------------------------------------------------
# Mission
# ---------------------------------------------------------------------------

MISSION_TERMINAL: FrozenSet[str] = frozenset({"completed", "failed", "cancelled"})

MISSION_TRANSITIONS: Dict[str, FrozenSet[str]] = {
    "draft": frozenset({"authorized", "cancelled"}),
    "authorized": frozenset({"executing", "cancelled", "failed"}),
    "executing": frozenset({"suspended", "completed", "failed", "cancelled"}),
    "suspended": frozenset({"executing", "cancelled", "failed"}),
    "completed": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
}


class MissionAggregate(object):
    """Owns mission lifecycle, objectives, criteria, and terminal state."""

    KIND = "mission"
    # State this aggregate is the SOLE authoritative writer of. Names are
    # qualified with the aggregate kind because a bare "state" means something
    # different in each aggregate; the disjointness test compares qualified
    # names so it measures real authority overlap, not naming coincidence.
    OWNED_FIELDS = frozenset(
        {
            "mission.state",
            "mission.objectives",
            "mission.successCriteria",
            "mission.terminationCriteria",
            "mission.taskGraphId",
            "mission.policyDecisionIds",
        }
    )
    # Read-only identifiers owned by another aggregate or by the mission spec.
    # Copied into the snapshot for correlation; never mutated here.
    REFERENCE_FIELDS = frozenset({"missionId"})

    @staticmethod
    def stream_id(mission_id: str) -> str:
        return "mission-" + mission_id

    @staticmethod
    def create(spec: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "missionId": spec["missionId"],
            "state": "draft",
            "objectives": [o["objectiveId"] for o in spec["objectives"]],
            "successCriteria": [c["criterionId"] for c in spec["successCriteria"]],
            "terminationCriteria": [c["criterionId"] for c in spec["terminationCriteria"]],
            "taskGraphId": spec.get("taskGraphId"),
            "policyDecisionIds": [],
        }

    @staticmethod
    def transition(state: Dict[str, Any], to_state: str) -> Dict[str, Any]:
        current = state["state"]
        if current in MISSION_TERMINAL:
            raise IllegalTransition(
                "mission %s is terminal" % state["missionId"], current, to_state
            )
        if to_state not in MISSION_TRANSITIONS.get(current, frozenset()):
            raise IllegalTransition("mission %s" % state["missionId"], current, to_state)
        nxt = dict(state)
        nxt["state"] = to_state
        return nxt

    @staticmethod
    def record_policy_decision(state: Dict[str, Any], decision_id: str) -> Dict[str, Any]:
        nxt = dict(state)
        ids = list(nxt["policyDecisionIds"])
        if decision_id not in ids:
            ids.append(decision_id)
        nxt["policyDecisionIds"] = ids
        return nxt


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

TASK_TERMINAL: FrozenSet[str] = frozenset({"succeeded", "failed", "cancelled"})

TASK_TRANSITIONS: Dict[str, FrozenSet[str]] = {
    "pending": frozenset({"ready", "cancelled"}),
    "ready": frozenset({"assigned", "cancelled"}),
    "assigned": frozenset({"running", "cancelled", "failed"}),
    "running": frozenset(
        {"awaiting_verification", "suspended", "succeeded", "failed", "cancelled"}
    ),
    "suspended": frozenset({"running", "cancelled", "failed"}),
    "awaiting_verification": frozenset({"succeeded", "failed", "cancelled"}),
    "succeeded": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
}


class TaskAggregate(object):
    """Owns task lifecycle, attempts, assignment, and recovery state."""

    KIND = "task"
    OWNED_FIELDS = frozenset(
        {
            "task.state",
            "task.attempt",
            "task.maxAttempts",
            "task.assignedDriverId",
            "task.recoveryState",
            "task.dependencies",
            "task.consequential",
        }
    )
    REFERENCE_FIELDS = frozenset({"taskId", "missionId"})

    @staticmethod
    def stream_id(task_id: str) -> str:
        return "task-" + task_id

    @staticmethod
    def create(node: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "taskId": node["taskId"],
            "missionId": node["missionId"],
            "state": node.get("state", "pending"),
            "attempt": node.get("attempt", 0),
            "maxAttempts": node.get("maxAttempts", 1),
            "assignedDriverId": node.get("assignedDriverId"),
            "recoveryState": node.get("recoveryState", "none"),
            "dependencies": node.get("dependencies", []),
            "consequential": node.get("consequential", False),
        }

    @staticmethod
    def transition(
        state: Dict[str, Any], to_state: str, driver_id: Optional[str] = None
    ) -> Dict[str, Any]:
        current = state["state"]
        if current in TASK_TERMINAL:
            raise IllegalTransition(
                "task %s is terminal" % state["taskId"], current, to_state
            )
        if to_state not in TASK_TRANSITIONS.get(current, frozenset()):
            raise IllegalTransition("task %s" % state["taskId"], current, to_state)
        nxt = dict(state)
        nxt["state"] = to_state
        if to_state == "running":
            nxt["attempt"] = int(state["attempt"]) + 1
            if nxt["attempt"] > int(state["maxAttempts"]):
                raise IllegalTransition(
                    "task %s exceeded maxAttempts %d"
                    % (state["taskId"], state["maxAttempts"]),
                    current,
                    to_state,
                )
        if driver_id is not None:
            nxt["assignedDriverId"] = driver_id
        return nxt
