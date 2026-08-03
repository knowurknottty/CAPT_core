"""Idempotent ContextPack assembly (M1-memory, ADR-DT-M1-MEM-001).

A ContextPack is built by CAPT from a mandatory memory query. It records
selected/excluded records, exclusion reasons, compression actions, summaries,
provenance retention, unresolved conflicts, stale records, redactions, token
budget, and a digest. Rebuild is idempotent for equivalent input state: the
same inputs produce the same digest; changed inputs change the digest.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Dict, List, Optional

from ..contracts import require
from .store import MemoryRecord, MemoryStore


def _select_records(
    store: MemoryStore,
    *,
    classes: List[str],
    project_scope: Optional[str],
    trust_threshold: float,
    consent_scope: Optional[str],
    sensitivity_allowance: Optional[str],
    token_budget: int,
    record_limit: int,
) -> tuple:
    """Return (selected contract dicts, excluded list, conflicts, stale ids).

    Selection respects token budget (estimated: 1 token ~= 4 chars). Records
    exceeding the budget are excluded with a reason. Consent/sensitivity
    filtering is applied HERE (the store returns all candidates via
    bypass_governance) and reported as exclusions so they remain visible.
    """
    candidates = store.query(
        classes=classes or None,
        project_scope=project_scope,
        trust_threshold=trust_threshold,
        limit=record_limit * 4,
        bypass_governance=True,
    )
    selected: List[Dict[str, Any]] = []
    excluded: List[Dict[str, Any]] = []
    conflicts: List[Dict[str, Any]] = []
    stale_ids: List[str] = []
    used_tokens = 0
    chars_per_token = 4.0

    # Consent/sensitivity governance ordering: public < project < user < secret.
    _order = {"public": 0, "project": 1, "user": 2, "secret": 3}

    # Simple relevance score: trust rank + recency + class match.
    trust_rank = {"capt_authoritative": 1.0, "verified": 0.8, "unverified": 0.4, "disputed": 0.1}
    for rec in candidates:
        # Consent gate: record consent must match the requested scope.
        if consent_scope is not None and rec.consent != consent_scope:
            excluded.append(
                {
                    "recordId": rec.record_id,
                    "reason": "consent scope mismatch (record consent=%s, requested=%s)"
                    % (rec.consent, consent_scope),
                }
            )
            continue
        # Sensitivity gate: record sensitivity must not exceed the allowance.
        if sensitivity_allowance is not None:
            if _order.get(rec.sensitivity, 3) > _order.get(sensitivity_allowance, 3):
                excluded.append(
                    {
                        "recordId": rec.record_id,
                        "reason": "sensitivity exceeds allowance (record=%s, allowance=%s)"
                        % (rec.sensitivity, sensitivity_allowance),
                    }
                )
                continue
        score = trust_rank.get(rec.trust, 0.3)
        reason = "selected by CAPT memory policy"
        if rec.stale:
            stale_ids.append(rec.record_id)
            reason = "selected but flagged stale"
        if rec.conflict_state:
            conflicts.append(
                {"recordId": rec.record_id, "conflictState": rec.conflict_state}
            )
        est_tokens = max(1, int(round(len(rec.content) / chars_per_token)))
        if token_budget and (used_tokens + est_tokens) > token_budget:
            excluded.append(
                {
                    "recordId": rec.record_id,
                    "reason": "token_budget exceeded",
                    "estimatedTokens": est_tokens,
                }
            )
            continue
        used_tokens += est_tokens
        selected.append(rec.with_retrieval(score, reason))

    return selected, excluded, conflicts, stale_ids


def build_context_pack(
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
    """Assemble a ContextPack. Deterministic for equivalent inputs."""
    classes = query.get("requestedMemoryClasses", [])
    selected, excluded, conflicts, stale_ids = _select_records(
        store,
        classes=classes,
        project_scope=query.get("projectScope"),
        trust_threshold=query.get("trustThreshold", 0.0),
        consent_scope=query.get("consentScope"),
        sensitivity_allowance=query.get("sensitivityAllowance"),
        token_budget=query.get("tokenBudget", 0),
        record_limit=query.get("recordLimit", 20),
    )
    context_usage_after = context_usage_before + sum(
        max(1, int(round(len(r.get("source", "")) / 4.0))) for r in []
    )  # selected content already counted in usage via selected_memory

    pack = {
        "schemaVersion": "1.0.0",
        "contextPackId": "cp-" + uuid.uuid4().hex[:12],
        "policyVersion": policy_version,
        "triggerBoundary": trigger_boundary,
        "contextUsageBefore": context_usage_before,
        "contextUsageAfter": context_usage_after,
        "selectedRecords": selected,
        "excludedRecords": excluded,
        "exclusionReasons": excluded,
        "compressionActions": compression_actions or [],
        "summariesGenerated": summaries or [],
        "provenanceRetained": True,
        "unresolvedConflicts": conflicts,
        "staleRecords": stale_ids,
        "redactions": redactions or [],
        "tokenBudget": query.get("tokenBudget", 0),
        "previousContextPackDigest": previous_digest,
        "missionId": mission_id,
        "taskId": task_id,
        "driverRunId": driver_run_id,
    }
    pack["contextPackDigest"] = _digest_pack(pack)
    require("ContextPack", pack)
    return pack


def _digest_pack(pack: Dict[str, Any]) -> str:
    """Stable digest over the semantically meaningful fields."""
    canon = json.dumps(
        {
            "policyVersion": pack["policyVersion"],
            "triggerBoundary": pack["triggerBoundary"],
            "contextUsageBefore": pack["contextUsageBefore"],
            "contextUsageAfter": pack["contextUsageAfter"],
            "selected": [
                {
                    "recordId": r["recordId"],
                    "digest": r["digest"],
                    "retrievalScore": r.get("retrievalScore"),
                }
                for r in pack["selectedRecords"]
            ],
            "excluded": [e.get("recordId") for e in pack["excludedRecords"]],
            "conflicts": pack["unresolvedConflicts"],
            "stale": pack["staleRecords"],
            "tokenBudget": pack["tokenBudget"],
            "missionId": pack["missionId"],
            "taskId": pack["taskId"],
            "driverRunId": pack["driverRunId"],
        },
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canon).hexdigest()
