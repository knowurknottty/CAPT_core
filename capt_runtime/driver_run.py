"""DriverRunAggregate (M0-B, ADR-0123).

Owns ONLY driver-run lifecycle and reconciliation. It must NOT own mission
lifecycle, task lifecycle, capability grants, claim verification, authoritative
evidence, or policy decisions.

States: created, queued, running, suspended, completed, cancelled, failed,
reconciliation_required, reconciled.

Terminal states are immutable except through an explicit reconciliation transition
where justified (lost -> reconciled).
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, Optional

from .errors import IllegalTransition

TERMINAL: FrozenSet[str] = frozenset(
    {"completed", "cancelled", "failed", "reconciled"}
)

TRANSITIONS: Dict[str, FrozenSet[str]] = {
    "created": frozenset({"queued", "cancelled", "failed"}),
    "queued": frozenset({"running", "cancelled", "failed"}),
    "running": frozenset({"suspended", "completed", "cancelled", "failed", "lost"}),
    "suspended": frozenset({"running", "cancelled", "failed"}),
    "lost": frozenset({"reconciled", "failed"}),
    "completed": frozenset(),
    "cancelled": frozenset(),
    "failed": frozenset(),
    "reconciled": frozenset(),
}


class DriverRunAggregate:
    KIND = "driverrun"

    OWNED_FIELDS = frozenset(
        {
            "driverrun.state",
            "driverrun.reconciliationStatus",
            "driverrun.workOrderVersion",
            "driverrun.externalRunId",
            "driverrun.attemptCount",
            "driverrun.observationSequence",
            "driverrun.cancellationState",
            "driverrun.suspensionState",
            "driverrun.checkpointRef",
            "driverrun.reconciliationState",
            "driverrun.budgetConsumed",
            "driverrun.terminalDisposition",
        }
    )
    REFERENCE_FIELDS = frozenset(
        {"driverRunId", "driverId", "missionId", "taskId"}
    )

    @staticmethod
    def stream_id(driver_run_id: str) -> str:
        return "driverrun-" + driver_run_id

    @staticmethod
    def create(run: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "driverRunId": run["driverRunId"],
            "driverId": run["driverId"],
            "missionId": run["missionId"],
            "taskId": run["taskId"],
            "workOrderVersion": run.get("workOrderVersion", 1),
            "externalRunId": run.get("externalRunId"),
            "state": "created",
            "reconciliationStatus": "not_required",
            "attemptCount": 0,
            "observationSequence": 0,
            "cancellationState": None,
            "suspensionState": None,
            "checkpointRef": None,
            "reconciliationState": None,
            "budgetConsumed": {"artifacts": 0, "observations": 0, "seconds": 0},
            "terminalDisposition": None,
        }

    @staticmethod
    def transition(
        state: Dict[str, Any], to_state: str, external_run_id: Optional[str] = None
    ) -> Dict[str, Any]:
        current = state["state"]
        if current in TERMINAL:
            raise IllegalTransition(
                "driver run %s is terminal" % state["driverRunId"], current, to_state
            )
        if to_state not in TRANSITIONS.get(current, frozenset()):
            raise IllegalTransition(
                "driver run %s" % state["driverRunId"], current, to_state
            )
        nxt = dict(state)
        nxt["state"] = to_state
        if external_run_id is not None:
            nxt["externalRunId"] = external_run_id
        if to_state == "running":
            nxt["attemptCount"] = int(state["attemptCount"]) + 1
        if to_state in ("completed", "cancelled", "failed"):
            nxt["terminalDisposition"] = to_state
        if to_state == "lost":
            nxt["reconciliationStatus"] = "required"
        if to_state == "reconciled":
            nxt["reconciliationStatus"] = state.get("reconciliationState") or "resolved_effect_absent"
        return nxt

    @staticmethod
    def next_observation_sequence(state: Dict[str, Any]) -> int:
        seq = int(state["observationSequence"]) + 1
        return seq
