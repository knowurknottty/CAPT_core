"""Driver reconciliation (M0-B, ADR-0124).

Reconciliation is a READ-ONLY CAPT procedure over the event ledger + driver-run
state. It emits a DriverReconciliationRecord listing detected anomalies and a
recommended disposition (DriverReconciliationResult). It performs NO driver
re-invocation and NO state mutation beyond recording the report.

No automatic retry of an indeterminate external action. M0-B is read-only, but the
same semantic discipline is established for M0-C.

Result enum:
- reconciled_completed
- reconciled_failed
- reconciliation_requires_human
- safe_to_retry
- retry_forbidden
- external_state_unknown
"""

from __future__ import annotations

from typing import Any, Dict, List

from .contracts import require

_VALID_RESULTS = frozenset(
    {
        "reconciled_completed",
        "reconciled_failed",
        "reconciliation_requires_human",
        "safe_to_retry",
        "retry_forbidden",
        "external_state_unknown",
    }
)


class ReconciliationError(Exception):
    pass


def classify_dispatch_boundary(dispatch_boundary: str) -> str:
    """Map a durable dispatch-boundary marker to a reconciliation disposition.

    Pure function over the boundary vocabulary; ``reconcile`` uses it for
    crash-recovered (lost) runs. Never fabricates certainty: a crossed
    request boundary without a completed response forbids automatic retry;
    a persisted result is harvestable; a pre-dispatch boundary is safe to
    retry only under fresh authority.
    """
    if dispatch_boundary in ("not_dispatched", "prepared", "budget_rejected"):
        return "safe_to_retry"
    if dispatch_boundary in ("request_started", "response_started"):
        return "retry_forbidden"
    if dispatch_boundary in ("response_completed", "result_persisted"):
        return "reconciled_completed"
    return "external_state_unknown"


def reconcile(
    driver_run_state: Dict[str, Any],
    ledger_events: List[Dict[str, Any]],
    observations: List[Dict[str, Any]],
    artifact_present: bool,
    lease_valid: bool,
    budget_valid: bool,
) -> Dict[str, Any]:
    """Produce a DriverReconciliationRecord. Read-only: returns a recommendation.

    Criteria:
    - artifact exists + completion event present + lease valid -> reconciled_completed
    - completion event missing but artifact exists -> reconciliation_requires_human
      (ambiguous terminal state; do NOT auto-promote)
    - artifact missing but completion event present -> reconciliation_requires_human
    - lease invalid/expired -> retry_forbidden (cannot safely re-run under stale lease)
    - budget invalid -> retry_forbidden
    - duplicate observations with conflicting payloads -> reconciliation_requires_human
    - orphaned run (no parent mission/task) -> reconciliation_requires_human
    - driver process interrupted (state 'lost') -> external_state_unknown
    """
    anomalies: List[str] = []
    run_id = driver_run_state["driverRunId"]

    if not driver_run_state.get("missionId") or not driver_run_state.get("taskId"):
        anomalies.append("orphaned run: missing mission/task binding")

    has_completion = any(
        e.get("eventType") == "DriverRunStateChanged"
        and e.get("payload", {}).get("toState") == "completed"
        for e in ledger_events
    )
    conflicting = _conflicting_observations(observations)
    if conflicting:
        anomalies.append("conflicting duplicate observations: %s" % conflicting)

    if not lease_valid:
        anomalies.append("capability lease invalid or expired")
    if not budget_valid:
        anomalies.append("budget invalid or exceeded")

    if driver_run_state["state"] == "lost":
        # P0.3: a lost run is classified from its durable dispatch-boundary
        # marker, not from guesswork. A crossed request boundary without a
        # completed response forbids automatic retry; a persisted result is
        # harvestable; a pre-dispatch boundary is safe to retry under fresh
        # authority. Anything else stays unknown.
        boundary = driver_run_state.get("dispatchBoundary", "unknown")
        disposition = classify_dispatch_boundary(boundary)
        if disposition == "safe_to_retry":
            result = "safe_to_retry"
            anomalies.append(
                "lost driver run with durable dispatch boundary %r: external dispatch "
                "provably never crossed; retry requires fresh authority" % (boundary,)
            )
        elif disposition == "retry_forbidden":
            result = "retry_forbidden"
            anomalies.append(
                "lost driver run with durable dispatch boundary %r: request crossed the "
                "provider boundary; external effect unknown; automatic retry forbidden" % (boundary,)
            )
        elif disposition == "reconciled_completed":
            if artifact_present:
                result = "reconciled_completed"
                anomalies.append(
                    "lost driver run with durable dispatch boundary %r and artifact present: "
                    "harvest the result; do not redispatch" % (boundary,)
                )
            else:
                result = "reconciliation_requires_human"
                anomalies.append(
                    "lost driver run with durable dispatch boundary %r but no artifact: "
                    "human decision required" % (boundary,)
                )
        else:
            result = "external_state_unknown"
            anomalies.append(
                "lost driver run with unknown dispatch boundary %r: external effects unknown" % (boundary,)
            )
    elif not lease_valid or not budget_valid:
        result = "retry_forbidden"
    elif has_completion and artifact_present:
        result = "reconciled_completed"
    elif has_completion and not artifact_present:
        result = "reconciliation_requires_human"
        anomalies.append("completion event present but artifact missing")
    elif artifact_present and not has_completion:
        result = "reconciliation_requires_human"
        anomalies.append("artifact present but completion event missing")
    else:
        result = "reconciliation_requires_human"

    if result not in _VALID_RESULTS:
        raise ReconciliationError("internal: invalid result %r" % result)

    record = {
        "schemaVersion": "1.0.0",
        "driverRunId": run_id,
        "result": result,
        "detectedAt": driver_run_state.get("createdAt", "2026-08-03T00:00:00Z"),
        "anomalies": anomalies,
    }
    return require("DriverReconciliationRecord", record)


def _conflicting_observations(observations: List[Dict[str, Any]]) -> List[str]:
    seen: Dict[str, Dict[str, Any]] = {}
    conflicts: List[str] = []
    for o in observations:
        oid = o.get("observationId")
        if oid in seen and seen[oid] != o:
            conflicts.append(oid)
        else:
            seen[oid] = o
    return conflicts
