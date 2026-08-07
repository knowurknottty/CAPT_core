"""Trusted resolution of a frozen work-order's mission/task references.

The driver wire contract carries identifiers only. This resolver runs inside
CAPT's authority boundary and derives bounded execution semantics exclusively
from authoritative aggregate state in EventStore.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from .aggregates.mission_task import TaskAggregate
from .errors import AuthorityViolation, NotFound
from .store import EventStore


@dataclass(frozen=True)
class ResolvedExecutionTask:
    mission_id: str
    task_id: str
    task_version: int
    objective: str
    state: str
    scope: Dict[str, Any]
    operations: tuple[str, ...]
    consequential: bool


class TaskResolver:
    """Resolve only persisted, executable task state for DriverHost dispatch."""

    def __init__(self, store: EventStore) -> None:
        self.store = store

    def resolve_for_execution(self, *, mission_id: str, task_id: str) -> ResolvedExecutionTask:
        if not self.store.load_state("mission-" + mission_id):
            raise NotFound("no mission %s" % mission_id)
        task = self.store.load_state(TaskAggregate.stream_id(task_id))
        if task is None:
            raise NotFound("no task %s" % task_id)
        if task.get("missionId") != mission_id:
            raise AuthorityViolation("task %s is not owned by mission %s" % (task_id, mission_id))
        if task.get("state") in {"cancelled", "failed", "succeeded"}:
            raise AuthorityViolation("task %s is terminal: %s" % (task_id, task.get("state")))
        objective = task.get("title")
        requirements = task.get("capabilityRequirements") or []
        if not isinstance(objective, str) or not objective.strip() or len(requirements) != 1:
            raise AuthorityViolation("task %s lacks a bounded executable objective" % task_id)
        requirement = requirements[0]
        scope = requirement.get("scope")
        operations = requirement.get("operations")
        if not isinstance(scope, dict) or not scope.get("rootPath") or not isinstance(operations, list) or not operations:
            raise AuthorityViolation("task %s lacks bounded capability scope" % task_id)
        return ResolvedExecutionTask(
            mission_id=mission_id, task_id=task_id,
            task_version=self.store.aggregate_version(TaskAggregate.stream_id(task_id)),
            objective=objective, state=task["state"], scope=dict(scope),
            operations=tuple(operations), consequential=bool(task.get("consequential")),
        )
