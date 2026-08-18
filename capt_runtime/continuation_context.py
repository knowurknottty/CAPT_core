"""Governed cross-model continuation context selection (PR #47 context gate).

This module realises the missing continuation path:

    AUTHORITATIVE PRIOR STATE
        -> CONTEXT SELECTION   (select_continuation_context)
        -> CONTEXT PACK
        -> CONTEXT PACK DIGEST
        -> MODEL-VISIBLE PROMPT
        -> APPROVAL BINDING
        -> PREPARED EXECUTION
        -> DISPATCH

A restarted runtime that has NO in-memory state reconstructs prior mission
cognition only by selecting authoritative durable evidence from the ledger.
Prior Model A output is selected here, never pasted by an operator, never
carried in a surviving Python object.

Trust discipline (Gate 7 / HY3 directive §7):
    Prior model output that has NOT been separately verified stays labeled
    ``unverified``.  Selection never upgrades evidence to verified truth.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Optional

_MARKER_RE = re.compile(r"(CAPT-CONTINUITY-[A-Za-z0-9_-]+|MK-[A-Za-z0-9_-]+)")


def _load(store, stream_id: str) -> Optional[Dict[str, Any]]:
    try:
        return store.load_state(stream_id)
    except Exception:
        return None


def _claim_for_task(store, task_id: str) -> Optional[Dict[str, Any]]:
    for stream_id, kind, _ in store.all_aggregates():
        if kind != "claim":
            continue
        st = _load(store, stream_id)
        if st and st.get("taskId") == task_id:
            return st
    return None


def _claim_verified(store, claim_id: Optional[str]) -> bool:
    if not claim_id:
        return False
    v = _load(store, "verification-" + claim_id)
    if isinstance(v, dict) and str(v.get("status", "")).lower().startswith("verified"):
        return True
    c = _load(store, "claim-" + claim_id)
    return bool(c and str(c.get("promotionState", "")).lower() == "verified")


def _artifact_paths_for_claim(claim_state: Optional[Dict[str, Any]]) -> List[str]:
    if not claim_state:
        return []
    out: List[str] = []
    for ev in claim_state.get("evidenceIds", []) or []:
        if isinstance(ev, dict) and ev.get("artifactPath"):
            out.append(ev["artifactPath"])
    return out


def _read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except Exception:
        return ""


def _extract_marker(content: str) -> Optional[str]:
    if not content:
        return None
    m = _MARKER_RE.search(content)
    return m.group(1) if m else None


def _digest_records(records: List[Dict[str, Any]], mission_id: str, task_id: str) -> str:
    canon = json.dumps(
        {
            "missionId": mission_id,
            "taskId": task_id,
            "records": [
                {
                    "recordId": r["recordId"],
                    "kind": r["kind"],
                    "trust": r["trust"],
                    "driverRunId": r.get("driverRunId"),
                    "contentDigest": hashlib.sha256(
                        r.get("content", "").encode("utf-8")
                    ).hexdigest(),
                }
                for r in records
            ],
        },
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canon).hexdigest()


def select_continuation_context(
    store,
    mission_id: str,
    task_id: str,
    *,
    exclude_run_id: Optional[str] = None,
    ledger_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Select authoritative prior mission evidence for a continuation run.

    Returns a deterministic pack: ``{records, contextPackDigest, missionId,
    taskId}``.  Each record carries a trust classification (``unverified`` unless
    a separate verification authority promoted its claim).  An empty selection
    yields an EMPTY pack digest (never the legacy placeholder).
    """
    records: List[Dict[str, Any]] = []
    for stream_id, kind, _ in store.all_aggregates():
        if kind != "driverrun":
            continue
        st = _load(store, stream_id)
        if not st:
            continue
        if st.get("missionId") != mission_id:
            continue
        if st.get("state") != "completed":
            continue
        rid = st.get("driverRunId")
        if exclude_run_id and rid == exclude_run_id:
            continue
        tid = st.get("taskId") or task_id
        claim_state = _claim_for_task(store, tid)
        trust = "verified" if _claim_verified(store, claim_state.get("claimId") if claim_state else None) else "unverified"
        for ap in _artifact_paths_for_claim(claim_state):
            content = _read_file(ap)
            marker = _extract_marker(content)
            records.append(
                {
                    "recordId": "cont-" + str(rid),
                    "kind": "prior_model_evidence",
                    "trust": trust,
                    "missionId": mission_id,
                    "taskId": tid,
                    "driverRunId": rid,
                    "artifactPath": ap,
                    "content": (marker or content or "")[:2000],
                    "marker": marker,
                    "provenance": {
                        "source": "prior_driverrun_evidence",
                        "driverRunId": rid,
                        "claimId": claim_state.get("claimId") if claim_state else None,
                    },
                }
            )
    digest = _digest_records(records, mission_id, task_id)
    return {
        "records": records,
        "contextPackDigest": digest,
        "missionId": mission_id,
        "taskId": task_id,
        "isEmpty": len(records) == 0,
    }


# Compatibility alias used by the brief's conceptual target architecture.
build_execution_context = select_continuation_context
