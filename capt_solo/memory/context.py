"""CAPT Solo v0.2 — Context Builder.

Single stable entry point: ``build_context(...)``. It orchestrates candidate
retrieval, CSG expansion, trust filtering, conflict handling, relevance ranking,
budget allocation, and AntiToken extraction into a model-neutral context packet.

The output is model-neutral: Hermes, Codex, Hy3, MIMO, or another model can
consume the same result. No model-specific prompt instructions are embedded.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from capt_solo.memory.antitoken import estimate_reduction, extract, render, validate
from capt_solo.memory.csg import CSG
from capt_solo.memory.models import (
    AntiTokenPacket,
    ContextBuildResult,
    ContextItem,
    MemoryKind,
)
from capt_solo.memory.trust import compute_trust, trust_from_kind


def build_context(
    engine,
    *,
    query: str = "",
    namespace: Optional[str] = None,
    tags: Optional[List[str]] = None,
    kinds: Optional[List[str]] = None,
    min_trust: float = 0.0,
    max_items: int = 10,
    char_budget: Optional[int] = None,
    token_budget: Optional[int] = None,
    include_superseded: bool = False,
    include_conflicts: bool = False,
    ctp_context: Optional[str] = None,
    session_context: Optional[str] = None,
    task_intent: Optional[str] = None,
) -> ContextBuildResult:
    """Build a model-neutral context packet from the local memory store.

    ``engine`` is a :class:`MemoryEngine` instance (caller owns lifecycle).
    """
    trace_id = uuid.uuid4().hex
    csg = CSG(engine._conn)
    candidates = engine._iter_all_for_context(namespace=namespace, tags=tags, kinds=kinds)
    # archived / rejected memories are excluded from active context by default
    candidates = [m for m in candidates
                  if (m.lifecycle_state or "active") not in ("archived", "rejected")]

    # trust scores
    trust_scores: Dict[str, float] = {}
    tx_linkage: Dict[str, str] = {}
    for m in candidates:
        kind = MemoryKind.from_tag(str((m.metadata or {}).get("kind", "fact")))
        base_state = trust_from_kind(kind)
        status = str((m.metadata or {}).get("status", "active"))
        score, _ = compute_trust(
            base_state,
            confidence=m.confidence,
            contradiction=bool((m.metadata or {}).get("contradiction", False)),
            superseded=(status == "superseded"),
            has_ctp_receipt=bool((m.metadata or {}).get("ctp_tx_id")),
        )
        trust_scores[m.memory_id] = score
        if ctp_context and (m.metadata or {}).get("ctp_tx_id") == ctp_context:
            tx_linkage[m.memory_id] = ctp_context

    # CSG selection
    cand_dicts = [m.to_dict() for m in candidates]
    selected, explanations = csg.select_context(
        cand_dicts,
        query=query, namespace=namespace, tags=tags,
        min_trust=min_trust, max_items=max_items,
        include_superseded=include_superseded,
        include_conflicts=include_conflicts,
        task_intent=task_intent, trust_scores=trust_scores,
        tx_linkage=tx_linkage,
    )
    selected_ids = {s["memory_id"] for s in selected}

    # AntiToken extraction + fidelity + budget allocation
    items: List[ContextItem] = []
    rendered_parts: List[str] = []
    src_chars = 0
    comp_chars = 0
    warnings: List[str] = []
    exclusions: List[Dict[str, Any]] = []
    conflicts: List[Dict[str, Any]] = []

    # build a quick lookup of source memories
    by_id = {m.memory_id: m for m in candidates}

    # allocate by selection order, respecting budget
    for s in selected:
        mid = s["memory_id"]
        mem = by_id.get(mid)
        if mem is None:
            continue
        pkt = extract(mem.to_dict())
        ok, fid_warn = validate(pkt, mem.to_dict())
        if not ok:
            # fidelity fallback: use a less compressed representation
            pkt.assertion = mem.content[:400]
            warnings.append(f"fidelity fallback for {mid}: " + "; ".join(fid_warn))
        # budget enforcement
        red = estimate_reduction(mem.content, pkt)
        if char_budget is not None and (comp_chars + red["compressed_chars"]) > char_budget:
            exclusions.append({"memory_id": mid, "reason": "char_budget exceeded"})
            continue
        if token_budget is not None and (comp_chars // 4 + red["estimated_compressed_tokens"]) > token_budget:
            exclusions.append({"memory_id": mid, "reason": "token_budget exceeded"})
            continue
        src_chars += red["source_chars"]
        comp_chars += red["compressed_chars"]
        items.append(ContextItem(
            memory_id=mid, score=s["score"], selected=True,
            reason="selected by CSG weighted algorithm",
            antitoken=pkt,
        ))
        rendered_parts.append(render(pkt, format="model_neutral"))

    # explanations for excluded (not in selected_ids)
    for e in explanations:
        if e["memory_id"] not in selected_ids:
            exclusions.append({
                "memory_id": e["memory_id"],
                "reason": e["reason"],
                "score": e["score"],
            })

    # conflicts surfaced
    for m in candidates:
        cf = csg.detect_conflicts(m.memory_id)
        if cf:
            conflicts.append({"memory_id": m.memory_id, "conflicts": cf})

    rendered = "\n".join(rendered_parts)
    reduction_ratio = 1.0 - (comp_chars / src_chars) if src_chars else 0.0

    return ContextBuildResult(
        query=query,
        items=items,
        rendered=rendered,
        exclusions=exclusions,
        conflicts=conflicts,
        warnings=warnings,
        estimated_source_chars=src_chars,
        estimated_compressed_chars=comp_chars,
        reduction_ratio=round(max(0.0, reduction_ratio), 4),
        trace_id=trace_id,
        config_snapshot={
            "max_items": max_items, "min_trust": min_trust,
            "char_budget": char_budget, "token_budget": token_budget,
            "include_superseded": include_superseded,
            "include_conflicts": include_conflicts,
            "csg_weights": csg.get_weights(),
        },
    )
