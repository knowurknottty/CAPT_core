"""Concrete cognitive-debt projection for CAPT operator surfaces (CAPT-UPG-024).

Debt is represented as source-linked unresolved conditions, never as an opaque
confidence/certainty score. The projection is read-only and cannot halt work or
mutate runtime state.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, List, Mapping, Optional

from capt_runtime.contracts import digest


def _verification_kind(value: Mapping[str, Any]) -> Optional[str]:
    status = value.get("status")
    if isinstance(status, Mapping):
        kind = status.get("kind")
        return str(kind) if kind else None
    if isinstance(status, str):
        return status
    return None


def _add(
    items: Dict[str, Dict[str, Any]],
    category: str,
    source_type: str,
    source_id: str,
    reason: str,
    *,
    blocking: bool,
    detail: Optional[Mapping[str, Any]] = None,
) -> None:
    debt_id = digest({
        "category": category,
        "sourceType": source_type,
        "sourceId": source_id,
        "reason": reason,
    })
    items[debt_id] = {
        "debtId": debt_id,
        "category": category,
        "sourceType": source_type,
        "sourceId": source_id,
        "reason": reason,
        "blocking": blocking,
        "detail": dict(detail or {}),
    }


def project_cognitive_debt(state: Mapping[str, Any]) -> Dict[str, Any]:
    items: Dict[str, Dict[str, Any]] = {}
    verifications = state.get("verificationsByClaim") or {}

    for claim in state.get("claims", []) or []:
        claim_id = str(claim.get("claimId") or "")
        if not claim_id:
            continue
        verification = verifications.get(claim_id, {}) if isinstance(verifications, Mapping) else {}
        kind = _verification_kind(verification) if isinstance(verification, Mapping) else None
        committed = bool(verification.get("committed")) if isinstance(verification, Mapping) else False

        if claim.get("requiresVerification") is True and not committed:
            _add(
                items, "required_claim_unverified", "claim", claim_id,
                "claim explicitly requires committed verification but none is recorded",
                blocking=True,
                detail={"verificationStatus": kind or "unknown"},
            )
        if kind == "contradicted" and claim.get("promotionState") not in ("rejected", "suppressed"):
            _add(
                items, "unresolved_contradiction", "claim", claim_id,
                "claim verification is contradicted without terminal rejection/suppression",
                blocking=True,
            )
        if claim.get("promotionState") == "qualified":
            _add(
                items, "qualified_claim", "claim", claim_id,
                "claim remains qualified rather than fully accepted/rejected",
                blocking=False,
                detail={"qualification": claim.get("qualification")},
            )
        if isinstance(verification, Mapping) and (
            verification.get("stale") is True or str(verification.get("freshness") or "").lower() == "stale"
        ):
            _add(
                items, "stale_verification_evidence", "claim", claim_id,
                "verification/evidence is explicitly marked stale",
                blocking=True,
            )

    for approval in state.get("approvals", []) or []:
        request_id = str(approval.get("requestId") or "")
        approval_state = str(approval.get("state") or "").lower()
        if request_id and approval_state in ("pending", "requested", "open", "awaiting_decision"):
            _add(
                items, "pending_approval", "human_approval", request_id,
                "human approval is still pending",
                blocking=True,
                detail={"operation": approval.get("operation")},
            )

    for task in state.get("tasks", []) or []:
        task_id = str(task.get("taskId") or "")
        recovery = str(task.get("recoveryState") or "none").lower()
        reconciliation = str(task.get("reconciliationStatus") or "").lower()
        if task_id and (recovery not in ("", "none", "clean") or reconciliation in ("required", "pending", "unknown")):
            _add(
                items, "task_recovery_required", "task", task_id,
                "task has unresolved recovery/reconciliation state",
                blocking=True,
                detail={"recoveryState": recovery, "reconciliationStatus": reconciliation},
            )

    for run in state.get("driverRuns", []) or []:
        run_id = str(run.get("driverRunId") or "")
        run_state = str(run.get("state") or "").lower()
        reconciliation = str(run.get("reconciliationStatus") or "").lower()
        occurrence = str(run.get("effectOccurrence") or run.get("externalEffectOccurrence") or "").lower()
        if run_id and (run_state in ("lost", "unknown", "reconciliation_required") or reconciliation in ("required", "pending", "unknown")):
            _add(
                items, "driver_reconciliation_required", "driver_run", run_id,
                "driver run has unresolved recovery/reconciliation state",
                blocking=True,
                detail={"state": run_state, "reconciliationStatus": reconciliation},
            )
        if run_id and occurrence in ("unknown", "indeterminate", "possibly_completed"):
            _add(
                items, "unknown_external_effect", "driver_run", run_id,
                "external effect occurrence is not known",
                blocking=True,
                detail={"effectOccurrence": occurrence},
            )

    for capability in state.get("capabilities", []) or []:
        grant_id = str(capability.get("grantId") or "")
        for reservation in capability.get("reservations", []) or []:
            if reservation.get("state") == "awaiting_reconciliation":
                reservation_id = str(reservation.get("reservationId") or "")
                _add(
                    items, "capability_reconciliation_required", "capability", grant_id,
                    "capability reservation awaits reconciliation",
                    blocking=True,
                    detail={"reservationId": reservation_id},
                )

    for cohort in state.get("cohorts", []) or []:
        cohort_id = str(cohort.get("cohortId") or "")
        current_epoch = int(cohort.get("epoch") or 0)
        for contribution in cohort.get("contributions", []) or []:
            contribution_id = str(contribution.get("contributionId") or "")
            epoch = int(contribution.get("epoch") or 0)
            outcome = str(contribution.get("outcome") or "").lower()
            material = bool(contribution.get("material"))
            if epoch < current_epoch:
                _add(
                    items, "stale_cohort_contribution", "cohort_contribution", contribution_id,
                    "contribution belongs to a prior deliberation epoch",
                    blocking=False,
                    detail={"cohortId": cohort_id, "contributionEpoch": epoch, "currentEpoch": current_epoch},
                )
            elif outcome in ("dissent", "escalate") and material:
                _add(
                    items, "unresolved_cohort_dissent", "cohort_contribution", contribution_id,
                    "material current-epoch dissent/escalation remains unresolved",
                    blocking=True,
                    detail={"cohortId": cohort_id, "outcome": outcome, "escalation": contribution.get("escalation")},
                )

    ordered = [items[key] for key in sorted(items)]
    categories = Counter(item["category"] for item in ordered)
    return {
        "schemaVersion": "1.0.0",
        "kind": "ConcreteCognitiveDebtProjection",
        "authority": "projection_only",
        "items": ordered,
        "categoryCounts": dict(sorted(categories.items())),
        "itemCount": len(ordered),
        "blockingItemCount": sum(1 for item in ordered if item["blocking"]),
        "opaqueScalarScore": None,
        "automaticHalt": False,
        "absenceOfDebtProvesCorrectness": False,
    }


def render_cognitive_debt(debt: Mapping[str, Any], max_items: int = 20) -> str:
    lines = [
        "CAPT Cognitive Debt — concrete unresolved conditions",
        "items=%d blocking=%d" % (
            int(debt.get("itemCount", 0)), int(debt.get("blockingItemCount", 0))
        ),
        "No opaque confidence score. Absence of recorded debt is not proof of correctness.",
    ]
    for item in list(debt.get("items", []) or [])[:max_items]:
        lines.append(
            "- %s | %s:%s | %s" % (
                item.get("category"), item.get("sourceType"), item.get("sourceId"), item.get("reason")
            )
        )
    remaining = int(debt.get("itemCount", 0)) - min(int(debt.get("itemCount", 0)), max_items)
    if remaining > 0:
        lines.append("... %d more debt item(s)" % remaining)
    return "\n".join(lines)
