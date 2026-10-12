"""Presentation-only helpers for the CAPT human Council workflow."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

from capt_ui.operator.council_workflow import CouncilWorkflow

PRESET_NAMES = ("Donor convergence (3 × 11)", "Blank Council")
_APPROVAL_STATE_LABELS = {
    "requested": ("Awaiting human approval", "pending"),
    "approved": ("Approved", "approved"),
    "denied": ("Denied", "error"),
    "consumed": ("Approval consumed", "neutral"),
    "expired": ("Expired", "error"),
    "revoked": ("Revoked", "error"),
}


def approval_presentation(state: str) -> tuple[str, str]:
    """A state label and semantic status; never invent runtime outcomes."""
    return _APPROVAL_STATE_LABELS.get(str(state), (str(state) or "Unknown", "neutral"))


def provider_catalog(manager: Any) -> dict[str, tuple[str, ...]]:
    """Return enabled configured providers and cached model indexes, without probing."""
    return {
        p.id: tuple(sorted(set(p.models)))
        for p in manager.list() if p.enabled
    }


def refresh_provider_models(manager: Any, provider_id: str) -> tuple[str, ...]:
    """Only called for an explicit human refresh action; model IDs remain editable."""
    provider = manager.get(provider_id)
    if not provider or not provider.enabled:
        raise ValueError("Choose an enabled registered provider")
    checked = manager.test(provider_id)
    if not checked.model_list_ok:
        raise RuntimeError("Provider model discovery unavailable; cached models retained")
    return tuple(sorted(set(checked.models)))


def draft_path(state_root: Path | None = None) -> Path:
    return (state_root or (Path.home() / ".capt")) / "ui" / "council-autosave.json"


def save_draft_snapshot(snapshot: Mapping[str, Any], path: Path) -> None:
    """Atomic owner-only convenience draft. Never includes approval/session receipts."""
    allowed = {"schemaVersion", "councilId", "missionId", "targetRoot",
               "maxConcurrentCohorts", "requestedContextBudget",
               "requestedExecutionSeconds", "responseMode", "promptEnhancement",
               "humanVerificationRequired", "fileMutationAllowed",
               "shellAccessAllowed", "providerNetworkPolicy",
               "charterSchemaVersion", "cohorts", "selectedCohort", "editorDraft", "pendingFields"}
    draft = {key: value for key, value in snapshot.items() if key in allowed}
    draft["schemaVersion"] = "1.0.0"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".council-autosave-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(draft, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def load_draft_snapshot(path: Path) -> CouncilWorkflow | None:
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Council draft must be an object")
    return CouncilWorkflow.from_mapping(raw).validate(require_target_exists=False)


def execution_projection(client: Any, executions: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Read-only, receipt-derived status lanes; absence is unknown, never success."""
    rows: list[dict[str, str]] = []
    for item in executions:
        run_id = str(item.get("driverRunId") or "")
        cohort = str((item.get("cohortSpec") or {}).get("cohortId") or "")
        try:
            state = client.get_state("driverrun-" + run_id) if run_id else {}
        except Exception:
            state = {}
        state = state if isinstance(state, dict) else {}
        diagnostic = ""
        if run_id and state.get("state") in ("lost", "failed"):
            try:
                reply = client._query({
                    "op": "provider_failure_diagnostic", "driverRunId": run_id
                })
                failure = reply.get("result") if isinstance(reply, dict) else None
                if isinstance(failure, dict):
                    parts = [str(failure.get("failureCode") or "provider failure")]
                    status = failure.get("httpStatus")
                    if type(status) is int:
                        parts.append("HTTP %d" % status)
                    calls = failure.get("providerHttpRequestAttempts")
                    if type(calls) is int:
                        parts.append("%d HTTP attempts" % calls)
                    diagnostic = " | ".join(parts)
            except Exception:
                # The canonical DriverRun state still determines the lane;
                # missing optional diagnostics never fabricate a success.
                pass
        rows.append({
            "cohortId": cohort,
            "driverRunId": run_id,
            "state": str(state.get("state") or "not dispatched / unknown"),
            "reconciliation": str(state.get("reconciliationStatus") or "unknown"),
            "diagnostic": diagnostic,
        })
    return rows


def mission_execution_projection(client: Any, workflow: CouncilWorkflow) -> list[dict[str, str]]:
    """Reattach read-only by deterministic mission/task/run IDs, never by approval."""
    executions = workflow.approval_payloads()
    return execution_projection(client, executions)


def execution_summary(rows: list[dict[str, str]]) -> tuple[str, str]:
    """Truthful GUI status, not a success/verification inference from provider text."""
    if not rows:
        return "No cohort runs configured", "unknown"
    states = {r.get("state", "").lower() for r in rows}
    reconciliation = [r for r in rows if r.get("reconciliation") == "required" or r.get("state") == "lost"]
    if reconciliation:
        names = ", ".join(r["cohortId"] for r in reconciliation)
        return "RECONCILIATION REQUIRED: " + names + ". Do not replay these provider calls.", "error"
    failed = [r for r in rows if r.get("state") in ("failed", "cancelled", "canceled")]
    if failed:
        return "FAILED: " + ", ".join(r["cohortId"] for r in failed), "error"
    if states & {"running", "submitted", "created", "queued", "pending"}:
        return "Provider dispatch in progress; completion is not yet proven.", "pending"
    if states == {"completed"}:
        return "Provider runs completed. Human verification and mission closure still required.", "review"
    if states & {"completed"}:
        return "Some provider runs completed; others are not confirmed. Inspect receipts.", "review"
    return "No authoritative DriverRuns found for this workflow.", "unknown"


def council_receipt_summary(receipt: Mapping[str, Any]) -> str:
    """Council command acceptance must not be mistaken for cohort success."""
    result = receipt.get("result")
    result = result if isinstance(result, dict) else {}
    rows = result.get("cohorts")
    rows = rows if isinstance(rows, list) else []
    rejected = []
    for item in rows:
        sub = item.get("receipt") if isinstance(item, dict) else {}
        sub = sub if isinstance(sub, dict) else {}
        if sub.get("status") not in ("accepted", "idempotent"):
            rejected.append(str(item.get("cohortId") or "unknown"))
    if rejected or result.get("outcome") == "incomplete":
        return "Council execution incomplete: " + ", ".join(rejected or result.get("unresolvedCohortIds") or [])
    if receipt.get("status") not in ("accepted", "idempotent"):
        return "Council dispatch rejected: " + str(receipt.get("classification") or receipt.get("status"))
    return "Council command returned; inspect DriverRun receipts and verification before declaring completion."


def existing_driver_run_conflicts(client: Any, workflow: CouncilWorkflow) -> list[str]:
    """Fail closed if IDs already have durable runs: retries need new IDs and approval."""
    conflicts: list[str] = []
    for item in workflow.approval_payloads():
        run_id = item["driverRunId"]
        try:
            state = client.get_state("driverrun-" + run_id)
        except Exception as exc:
            if "unknown stream" in str(exc).lower():
                continue
            raise
        if isinstance(state, dict) and state:
            conflicts.append("%s (%s)" % (run_id, state.get("state", "unknown")))
    return conflicts


def existing_council_receipt_conflict(client: Any, workflow: CouncilWorkflow) -> str:
    """The durable Council receipt ID is immutable independently of mission IDs."""
    reply = client._query({
        "op": "council_receipt", "councilId": workflow.council_id,
    })
    record = reply.get("result") if isinstance(reply, dict) else None
    if not isinstance(record, dict) or not record:
        return ""
    return "%s (%s, replayForbidden=%s)" % (
        workflow.council_id,
        record.get("state", "unknown"),
        bool(record.get("replayForbidden", True)),
    )
