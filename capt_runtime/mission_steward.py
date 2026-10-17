"""CAPT Mission Steward: read-only backlog inventory and diagnosis.

The steward classifies missions from RuntimeService read models and produces
RUN / RESUME / VERIFY / COMPLETE / KILL_REVIEW / INVESTIGATE / HUMAN_DECISION
recommendations. It never dispatches, resumes, cancels, or mutates mission
state: the only runtime surface it consumes is ``client.query``. Execution and
termination remain governed CAPT operations requiring explicit operator
authorization per action.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping

MODE_READ_ONLY_DIAGNOSIS = "READ_ONLY_DIAGNOSIS"
SCHEMA_VERSION = "1.0.0"

DISPOSITION_RUN = "RUN"
DISPOSITION_RESUME = "RESUME"
DISPOSITION_VERIFY = "VERIFY"
DISPOSITION_COMPLETE = "COMPLETE"
DISPOSITION_KILL_REVIEW = "KILL_REVIEW"
DISPOSITION_INVESTIGATE = "INVESTIGATE"
DISPOSITION_HUMAN_DECISION = "HUMAN_DECISION"
DISPOSITION_RETAIN = "RETAIN"
DISPOSITION_UNKNOWN = "UNKNOWN"

# Query operations the steward is allowed to use. Anything else is a bug:
# diagnosis must stay on the read surface.
READ_ONLY_QUERY_OPS = frozenset({
    "list_aggregates", "missions", "tasks", "approvals",
    "get_state", "get_stream_events", "bots",
})

STEWARD_BOT_ID = "capt-mission-steward"


def build_steward_bot_manifest() -> dict[str, Any]:
    """BotManifest payload for register_bot (createdBy/createdAt are injected
    by the command service from the authenticated operator; including them is
    rejected as spoofing)."""
    return {
        "schemaVersion": SCHEMA_VERSION,
        "botId": STEWARD_BOT_ID,
        "displayName": "CAPT Mission Steward",
        "roleKind": "crew",
        "role": "mission_steward",
        "missionId": None,
        "modelStrategy": {"primary": None, "fallbacks": []},
        "cognitionPolicy": {"promotionMode": "locked"},
        "localityPolicy": {"defaultRuntime": "local", "privateData": "local_only"},
        "collaboration": {"mayDelegate": False, "maxSpawnDepth": 0},
        "authorityTemplateRef": None,
    }


def _counts(rows: Iterable[Mapping[str, Any]], key: str = "state") -> dict[str, int]:
    return dict(Counter(str(r.get(key)) for r in rows))


def _project_for(mission: Mapping[str, Any], tasks: list[Mapping[str, Any]],
                 approvals: list[Mapping[str, Any]]) -> str:
    spec = mission.get("spec") if isinstance(mission.get("spec"), dict) else {}
    for constraint in spec.get("constraints") or []:
        if isinstance(constraint, dict) and constraint.get("field") == "workspace.rootPath":
            value = str(constraint.get("mustEqual") or "")
            if value:
                return value
    for approval in approvals:
        resource = str(approval.get("resource") or "")
        if resource.startswith("/"):
            return resource
    return "unattributed"


def classify_mission(
    mission: Mapping[str, Any],
    tasks: list[Mapping[str, Any]],
    approvals: list[Mapping[str, Any]],
    driver_runs: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Derive an operational disposition from evidence. The stored lifecycle
    ``state`` is never rewritten or reinterpreted here; the disposition is a
    recommendation layered on top of it."""
    state = str(mission.get("state"))
    task_states = _counts(tasks)
    approval_states = _counts(approvals)
    run_states = dict(Counter(str(r.get("status") or r.get("state")) for r in driver_runs))

    awaiting_verification = task_states.get("awaiting_verification", 0)
    failed_tasks = task_states.get("failed", 0)
    pending_tasks = task_states.get("pending", 0)
    suspended_tasks = task_states.get("suspended", 0)
    succeeded_tasks = task_states.get("succeeded", 0)
    cancelled_tasks = task_states.get("cancelled", 0)
    lost_runs = run_states.get("lost", 0)
    failed_runs = run_states.get("failed", 0)
    recon_required = sum(
        1 for r in driver_runs if r.get("reconciliationStatus") == "required"
    )
    awaiting_decision = approval_states.get("requested", 0)
    approved_unconsumed = [
        a for a in approvals
        if a.get("state") == "approved" and (a.get("expired") or (a.get("derived") or {}).get("expired"))
    ]
    denied = approval_states.get("denied", 0)

    if state == "completed":
        disposition, reason, confidence = (
            DISPOSITION_RETAIN,
            "Mission lifecycle is completed; retain as historical record.",
            "high",
        )
    elif awaiting_verification:
        disposition, reason, confidence = (
            DISPOSITION_VERIFY,
            (f"{awaiting_verification} task(s) awaiting verification; DriverRun "
            "evidence exists and must be witnessed before any replay or resume."),
            "high",
        )
    elif lost_runs or recon_required:
        disposition, reason, confidence = (
            DISPOSITION_INVESTIGATE,
            (f"{lost_runs} lost DriverRun(s), {recon_required} requiring "
            "reconciliation; outcome is ambiguous and must be reconciled, "
            "never blind-retried."),
            "high",
        )
    elif failed_tasks or failed_runs:
        disposition, reason, confidence = (
            DISPOSITION_INVESTIGATE,
            (f"{failed_tasks} failed task(s), {failed_runs} failed DriverRun(s); "
            "diagnose the failure signature before any retry."),
            "high" if failed_tasks + failed_runs > 1 else "medium",
        )
    elif awaiting_decision:
        disposition, reason, confidence = (
            DISPOSITION_HUMAN_DECISION,
            f"{awaiting_decision} approval(s) awaiting a human decision.",
            "high",
        )
    elif approved_unconsumed:
        disposition, reason, confidence = (
            DISPOSITION_HUMAN_DECISION,
            (f"{len(approved_unconsumed)} approved approval(s) expired before "
            "consumption; requires a fresh human decision, not auto-consumption."),
            "medium",
        )
    elif denied and not tasks:
        disposition, reason, confidence = (
            DISPOSITION_KILL_REVIEW,
            ("Approval denied and no tasks were ever created; candidate to "
            "close/archive (never delete receipts)."),
            "medium",
        )
    elif tasks and succeeded_tasks + cancelled_tasks == len(tasks):
        if succeeded_tasks:
            disposition, reason, confidence = (
                DISPOSITION_COMPLETE,
                ("All tasks reached terminal states with at least one success; "
                "candidate for governed completion/closure review."),
                "medium",
            )
        else:
            disposition, reason, confidence = (
                DISPOSITION_KILL_REVIEW,
                "All tasks cancelled with no successes; candidate to close/archive.",
                "medium",
            )
    elif suspended_tasks:
        disposition, reason, confidence = (
            DISPOSITION_RESUME,
            (f"{suspended_tasks} suspended task(s) with no blocking terminal "
            "failure; resumable only through governed approval."),
            "medium",
        )
    elif pending_tasks and not driver_runs:
        disposition, reason, confidence = (
            DISPOSITION_RUN,
            ("Tasks pending and no DriverRun history; apparently never "
            "dispatched. RUN still requires fresh governed approval, cost "
            "review, and revalidation against current head."),
            "medium",
        )
    elif pending_tasks:
        disposition, reason, confidence = (
            DISPOSITION_RESUME,
            ("Tasks pending with prior DriverRun history; treat as resume "
            "candidate, revalidate before dispatch."),
            "medium",
        )
    else:
        disposition, reason, confidence = (
            DISPOSITION_UNKNOWN,
            "Evidence does not support a confident disposition; inspect manually.",
            "low",
        )

    title = ""
    spec = mission.get("spec") if isinstance(mission.get("spec"), dict) else {}
    for field in ("objective", "normalizedRequest", "canonicalSpec"):
        value = spec.get(field)
        if isinstance(value, str) and value.strip():
            title = value.strip()[:300]
            break
    if not title and tasks:
        title = str(tasks[0].get("title") or "")[:300]

    return {
        "missionId": mission.get("missionId"),
        "title": title,
        "project": _project_for(mission, tasks, approvals),
        "storedState": state,
        "disposition": disposition,
        "reason": reason,
        "confidence": confidence,
        "requiredAuthority": (
            "none (read-only diagnosis)"
            if disposition in (DISPOSITION_RETAIN, DISPOSITION_INVESTIGATE)
            else "explicit operator authorization per mission, with revalidation"
        ),
        "taskCounts": task_states,
        "driverRunCounts": run_states,
        "approvalCounts": approval_states,
        "createdAt": mission.get("createdAt"),
    }


def fetch_inventory(client: Any) -> dict[str, Any]:
    """Assemble a read-only inventory through typed RuntimeService queries.

    ``client`` must expose ``query(op, payload)`` (e.g. RuntimeIPCClient).
    Only operations in READ_ONLY_QUERY_OPS are used."""
    def q(op: str, payload: dict | None = None) -> Any:
        if op not in READ_ONLY_QUERY_OPS:
            raise ValueError(f"mission steward may not use query op {op!r}")
        return client.query(op, payload or {})

    aggregates = q("list_aggregates")
    by_kind: dict[str, list[dict]] = {}
    for aggregate in aggregates:
        if isinstance(aggregate, dict):
            by_kind.setdefault(str(aggregate.get("kind")), []).append(aggregate)

    missions = q("missions", {"limit": 100000}).get("missions") or []
    tasks = q("tasks", {"limit": 100000}).get("tasks") or []
    approvals = q("approvals", {"limit": 100000}).get("approvals") or []
    bots = (q("bots", {"limit": 100000}).get("bots") or [])

    driver_runs: list[dict] = []
    for aggregate in by_kind.get("driverrun", []):
        state = q("get_state", {"streamId": aggregate["streamId"]})
        if isinstance(state, dict):
            driver_runs.append(state)

    return {
        "missions": missions,
        "tasks": tasks,
        "approvals": approvals,
        "driverRuns": driver_runs,
        "bots": bots,
        "aggregateCounts": {k: len(v) for k, v in sorted(by_kind.items())},
    }


def build_decision_report(inventory: Mapping[str, Any]) -> dict[str, Any]:
    """Classify every mission and summarize. Mode is always read-only."""
    missions = list(inventory.get("missions") or [])
    tasks_by_mission: dict[str, list[dict]] = {}
    for task in inventory.get("tasks") or []:
        tasks_by_mission.setdefault(str(task.get("missionId")), []).append(task)
    approvals_by_mission: dict[str, list[dict]] = {}
    for approval in inventory.get("approvals") or []:
        approvals_by_mission.setdefault(str(approval.get("missionId")), []).append(approval)
    runs_by_mission: dict[str, list[dict]] = {}
    for run in inventory.get("driverRuns") or []:
        runs_by_mission.setdefault(str(run.get("missionId")), []).append(run)

    rows = [
        classify_mission(
            mission,
            tasks_by_mission.get(str(mission.get("missionId")), []),
            approvals_by_mission.get(str(mission.get("missionId")), []),
            runs_by_mission.get(str(mission.get("missionId")), []),
        )
        for mission in missions
    ]
    return {
        "schema": "capt-mission-steward/decisions-v1",
        "mode": MODE_READ_ONLY_DIAGNOSIS,
        "totalMissions": len(rows),
        "classified": sum(1 for r in rows if r["disposition"] != DISPOSITION_UNKNOWN),
        "unknown": sum(1 for r in rows if r["disposition"] == DISPOSITION_UNKNOWN),
        "byDisposition": dict(Counter(r["disposition"] for r in rows)),
        "byProject": dict(Counter(r["project"] for r in rows)),
        "rows": rows,
    }
