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
        rows.append({
            "cohortId": cohort,
            "driverRunId": run_id,
            "state": str(state.get("state") or "not dispatched / unknown"),
            "reconciliation": str(state.get("reconciliationStatus") or "unknown"),
        })
    return rows
