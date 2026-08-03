"""Context selection / reduction / packaging pipeline (ADR-DT-PLANE-CONV, Gate 7).

The context pipeline is split into distinct, auditable stages. Each stage
records its inputs, policy, selected/excluded records, reasons, trust, consent,
token/size budget, digest, and reproducibility data. Retrieval algorithms may
evolve within a stage without changing the ContextPack wire contract.

Stages (per workflow Gate 7):

    durable data and memory
    -> Knowledge Bubble selection      (select_knowledge_bubbles)
    -> context selection               (select_context)
    -> context reduction/compression   (reduce_context)
    -> ContextSlice construction       (build_context_slice_stage)
    -> ContextPack packaging           (package_context_pack)

No driver receives raw memory outside the authorized ContextPack slice.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .contracts import require
from .memory.contextpack import build_context_pack as _package_context_pack
from .memory.store import MemoryRecord, MemoryStore


def _stage_digest(stage: str, payload: Any) -> str:
    canon = json.dumps({"stage": stage, "payload": payload}, sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(canon).hexdigest()


def select_knowledge_bubbles(
    store: MemoryStore,
    *,
    classes: List[str],
    project_scope: Optional[str],
    record_limit: int = 20,
) -> Dict[str, Any]:
    """Stage 1 — Knowledge Bubble selection.

    Choose candidate memory bubbles relevant to the mission from durable data.
    Returns selected bubble descriptors + the stage digest for reproducibility.
    """
    candidates = store.query(
        classes=classes or None,
        project_scope=project_scope,
        limit=record_limit * 4,
        bypass_governance=True,
    )
    bubbles = [
        {
            "recordId": c.record_id,
            "memoryClass": c.memory_class,
            "trust": c.trust,
            "sensitivity": c.sensitivity,
            "consent": c.consent,
        }
        for c in candidates
    ]
    return {
        "stage": "knowledge_bubble_selection",
        "inputs": {"classes": classes, "projectScope": project_scope, "recordLimit": record_limit},
        "selectedBubbles": bubbles,
        "selectedCount": len(bubbles),
        "stageDigest": _stage_digest("knowledge_bubble_selection", bubbles),
    }


def select_context(
    store: MemoryStore,
    *,
    classes: List[str],
    project_scope: Optional[str],
    trust_threshold: float = 0.0,
    consent_scope: Optional[str] = None,
    sensitivity_allowance: Optional[str] = None,
    token_budget: int = 0,
    record_limit: int = 20,
) -> Dict[str, Any]:
    """Stage 2 — context selection.

    Apply consent/sensitivity/token governance to choose which records enter
    context. Excluded records remain visible with reasons.
    """
    selected, excluded, conflicts, stale_ids = _select_records(
        store,
        classes=classes,
        project_scope=project_scope,
        trust_threshold=trust_threshold,
        consent_scope=consent_scope,
        sensitivity_allowance=sensitivity_allowance,
        token_budget=token_budget,
        record_limit=record_limit,
    )
    return {
        "stage": "context_selection",
        "inputs": {
            "classes": classes, "projectScope": project_scope,
            "trustThreshold": trust_threshold, "consentScope": consent_scope,
            "sensitivityAllowance": sensitivity_allowance, "tokenBudget": token_budget,
        },
        "selectedRecords": selected,
        "excludedRecords": excluded,
        "unresolvedConflicts": conflicts,
        "staleRecords": stale_ids,
        "selectedCount": len(selected),
        "excludedCount": len(excluded),
        "stageDigest": _stage_digest("context_selection", [selected, excluded]),
    }


def reduce_context(
    selected_records: List[Dict[str, Any]],
    *,
    token_budget: int = 0,
) -> Dict[str, Any]:
    """Stage 3 — context reduction / compression.

    Produce a reduced, budget-bounded view. Compression actions are recorded.
    The original selected records are preserved; reduction is additive metadata.
    """
    used = 0
    reduced = []
    compression_actions: List[Dict[str, Any]] = []
    for rec in selected_records:
        est = rec.get("estimatedTokens", max(1, int(round(len(rec.get("source", "")) / 4.0))))
        if token_budget and (used + est) > token_budget:
            compression_actions.append({
                "recordId": rec["recordId"], "action": "deferred", "reason": "token_budget",
            })
            continue
        used += est
        reduced.append(rec)
    return {
        "stage": "context_reduction",
        "inputs": {"tokenBudget": token_budget, "recordCount": len(selected_records)},
        "reducedRecords": reduced,
        "compressionActions": compression_actions,
        "reducedCount": len(reduced),
        "stageDigest": _stage_digest("context_reduction", [reduced, compression_actions]),
    }


def build_context_slice_stage(
    reduced_records: List[Dict[str, Any]],
    *,
    context_pack_digest: str = "sha256:" + "0" * 64,
    mission_id: Optional[str] = None,
    task_id: Optional[str] = None,
    driver_run_id: Optional[str] = None,
    operations: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Stage 4 — ContextSlice construction (memory-context reference).

    Build the minimized, driver-facing memory-context slice reference. It carries
    only the ContextPack digest and selected-record count plus mission/task
    linkage — raw memory content is NEVER forwarded (disclosure guard). The full
    execution ContextSlice (lease/filesystem policy/etc.) is constructed
    separately by capt_runtime.context_slice.build_context_slice at dispatch.
    """
    slice_obj = {
        "schemaVersion": "1.0.0",
        "kind": "memory_context_slice",
        "contextPackDigest": context_pack_digest,
        "selectedRecordCount": len(reduced_records),
        "missionId": mission_id,
        "taskId": task_id,
        "driverRunId": driver_run_id,
        "operations": operations or ["RepositoryRead"],
    }
    return {
        "stage": "context_slice_construction",
        "inputs": {"reducedCount": len(reduced_records)},
        "contextSlice": slice_obj,
        "stageDigest": _stage_digest("context_slice_construction", slice_obj),
    }


def package_context_pack(
    *,
    store: MemoryStore,
    policy_version: int,
    trigger_boundary: int,
    context_usage_before: int,
    query: Dict[str, Any],
    mission_id: Optional[str] = None,
    task_id: Optional[str] = None,
    driver_run_id: Optional[str] = None,
    previous_digest: Optional[str] = None,
    compression_actions: Optional[List[Dict[str, Any]]] = None,
    summaries: Optional[List[str]] = None,
    redactions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Stage 5 — ContextPack packaging.

    Assemble the authoritative, digest-stamped ContextPack. Delegates to the
    canonical ``build_context_pack`` (idempotent, contract-validated).
    """
    pack = _package_context_pack(
        store=store,
        policy_version=policy_version,
        trigger_boundary=trigger_boundary,
        context_usage_before=context_usage_before,
        query=query,
        mission_id=mission_id,
        task_id=task_id,
        driver_run_id=driver_run_id,
        previous_digest=previous_digest,
        compression_actions=compression_actions,
        summaries=summaries,
        redactions=redactions,
    )
    return pack


def run_pipeline(
    store: MemoryStore,
    *,
    policy_version: int,
    trigger_boundary: int,
    context_usage_before: int,
    query: Dict[str, Any],
    mission_id: Optional[str] = None,
    task_id: Optional[str] = None,
    driver_run_id: Optional[str] = None,
    previous_digest: Optional[str] = None,
) -> Dict[str, Any]:
    """Compose all five stages into one auditable run.

    Returns each stage's output plus the final ContextPack. Each stage is
    independently reproducible via its stageDigest.
    """
    classes = query.get("requestedMemoryClasses", [])
    bubble_stage = select_knowledge_bubbles(
        store, classes=classes, project_scope=query.get("projectScope"))
    selection_stage = select_context(
        store,
        classes=classes,
        project_scope=query.get("projectScope"),
        trust_threshold=query.get("trustThreshold", 0.0),
        consent_scope=query.get("consentScope"),
        sensitivity_allowance=query.get("sensitivityAllowance"),
        token_budget=query.get("tokenBudget", 0),
        record_limit=query.get("recordLimit", 20),
    )
    reduction_stage = reduce_context(
        selection_stage["selectedRecords"], token_budget=query.get("tokenBudget", 0))
    pack = package_context_pack(
        store=store, policy_version=policy_version, trigger_boundary=trigger_boundary,
        context_usage_before=context_usage_before, query=query,
        mission_id=mission_id, task_id=task_id, driver_run_id=driver_run_id,
        previous_digest=previous_digest,
        compression_actions=reduction_stage["compressionActions"])
    slice_stage = build_context_slice_stage(
        reduction_stage["reducedRecords"],
        context_pack_digest=pack["contextPackDigest"],
        mission_id=mission_id, task_id=task_id, driver_run_id=driver_run_id)

    return {
        "stages": {
            "knowledge_bubble_selection": bubble_stage,
            "context_selection": selection_stage,
            "context_reduction": reduction_stage,
            "context_slice_construction": slice_stage,
        },
        "contextPack": pack,
    }


# Re-export the internal selector so the pipeline owns the selection contract.
def _select_records(store, *, classes, project_scope, trust_threshold,
                    consent_scope, sensitivity_allowance, token_budget, record_limit):
    from .memory.contextpack import _select_records as _sr
    return _sr(
        store,
        classes=classes, project_scope=project_scope, trust_threshold=trust_threshold,
        consent_scope=consent_scope, sensitivity_allowance=sensitivity_allowance,
        token_budget=token_budget, record_limit=record_limit)
