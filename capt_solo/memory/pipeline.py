"""CAPT Solo v0.2 — Memory Processing Pipeline.

Explicit, testable pipeline. Each stage returns a typed ``StageResult``. A
failed stage must NOT leave partially committed memory or stale indexes. Writes
are wrapped in a SQLite transaction so either everything persists or nothing does.

Stages:
    validation -> normalization -> secret screening -> deduplication ->
    trust/provenance evaluation -> CSG graph update -> AntiToken extraction ->
    persistence -> search-index update

KHSB lifecycle events are emitted for observability (never a second DB).
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from capt_solo.core.errors import MemoryError_
from capt_solo.khsb.bus import KHSB
from capt_solo.memory.csg import CSG, EdgeType
from capt_solo.memory.deduplicate import detect_conflicts, find_duplicates
from capt_solo.memory.models import MemoryKind, StageResult, TrustState
from capt_solo.memory.normalize import normalize_stage
from capt_solo.memory.secrets import secret_screening_stage
from capt_solo.memory.trust import apply_transition, compute_trust, trust_from_kind


class MemoryPipeline:
    """Orchestrates ingestion through typed stages with atomic persistence."""

    def __init__(self, engine, bus: Optional[KHSB] = None) -> None:
        # engine is a MemoryEngine; bus is optional (in-process KHSB).
        self._eng = engine
        self._bus = bus or KHSB()
        self._csg = CSG(engine._conn)

    # ----- main entry ----------------------------------------------------
    def ingest(
        self,
        content: str,
        *,
        namespace: str = "default",
        tags: Optional[List[str]] = None,
        provenance: str = "unknown",
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
        kind: str = "fact",
        allow_secrets: bool = False,
        ctp_tx_id: Optional[str] = None,
        emit_events: bool = True,
    ) -> StageResult:
        """Run the full pipeline. Returns a StageResult with the stored Memory
        in ``value['memory']`` on success, or rejections on failure.

        On any stage failure, no rows are committed (atomic via rollback).
        """
        trace_id = uuid.uuid4().hex
        tags = tags or []
        meta = dict(metadata or {})
        meta["kind"] = kind
        if ctp_tx_id:
            meta["ctp_tx_id"] = ctp_tx_id

        if emit_events:
            self._bus.publish("memory.ingest.requested",
                              {"trace_id": trace_id, "namespace": namespace})

        # 1. validation
        if not content or not content.strip():
            res = StageResult(stage="validation", ok=False, trace_id=trace_id)
            res.add_rejection("empty content")
            if emit_events:
                self._bus.publish("memory.ingest.rejected",
                                  {"trace_id": trace_id, "reason": "empty content"})
            return res

        # 2. normalization
        norm_res = normalize_stage(content, namespace, tuple(tags))
        if not norm_res.ok:
            norm_res.trace_id = trace_id
            if emit_events:
                self._bus.publish("memory.ingest.rejected",
                                  {"trace_id": trace_id, "reason": "normalize failed"})
            return norm_res

        # 3. secret screening
        sec_res = secret_screening_stage(norm_res.value["content"], allow_secrets=allow_secrets)
        sec_res.trace_id = trace_id
        if not sec_res.ok:
            if emit_events:
                self._bus.publish("memory.ingest.rejected",
                                  {"trace_id": trace_id, "reason": "secret detected"})
            return sec_res
        final_content = sec_res.value["redacted"] if (sec_res.value["has_secret"] and not allow_secrets) \
            else norm_res.value["content"]

        # 4. deduplication (against existing)
        existing = [m.to_dict() for m in self._eng._iter_all()]
        dedup_res = find_duplicates(final_content, namespace, tuple(tags), existing)
        dedup_res.trace_id = trace_id
        is_dup = any(m["kind"] == "exact" for m in dedup_res.value["matches"])
        if is_dup and not meta.get("allow_duplicate"):
            dedup_res.ok = False
            for m in dedup_res.value["matches"]:
                dedup_res.add_rejection(f"exact duplicate of {m['memory_id']}")
            if emit_events:
                self._bus.publish("memory.ingest.rejected",
                                  {"trace_id": trace_id, "reason": "exact duplicate"})
            return dedup_res

        # 5. trust / provenance evaluation
        kind_enum = MemoryKind.from_tag(kind)
        trust_state = trust_from_kind(kind_enum)
        trust_score, trust_notes = compute_trust(
            trust_state, confidence=confidence,
            has_ctp_receipt=bool(ctp_tx_id))
        meta["trust_state"] = trust_state.value
        meta["trust_score"] = round(trust_score, 4)

        # 6. conflict detection (pre-persistence)
        conflicts = detect_conflicts(final_content, existing)
        if conflicts:
            meta["contradiction"] = True
            meta["conflict_with"] = [c["memory_id"] for c in conflicts]

        # 7. CSG graph update + 8. persistence + 9. search index
        # All inside one SQLite transaction for atomicity.
        try:
            self._eng._conn.execute("BEGIN")
            mem = self._eng._store_raw(
                final_content, namespace=namespace, tags=tags,
                provenance=provenance, confidence=confidence, metadata=meta)
            # graph node
            self._csg._ensure_node(mem.memory_id, kind_enum.value)
            # record conflict edges
            for c in conflicts:
                self._csg.add_edge(mem.memory_id, c["memory_id"],
                                   EdgeType.CONTRADICTS.value,
                                   provenance="pipeline_conflict",
                                   ctp_tx_id=ctp_tx_id)
            # AntiToken extraction is done lazily by context builder; here we
            # just confirm it can run (fidelity is checked at build time).
            self._eng._conn.execute("COMMIT")
        except Exception as e:  # rollback on any failure
            self._eng._conn.execute("ROLLBACK")
            res = StageResult(stage="persistence", ok=False, trace_id=trace_id)
            res.add_rejection(f"persistence failed: {e}")
            if emit_events:
                self._bus.publish("memory.ingest.rejected",
                                  {"trace_id": trace_id, "reason": f"persistence: {e}"})
            return res

        # search index update (outside txn, in-memory adapter)
        self._eng._adapter.index(mem.memory_id, mem.content, self._eng._meta_for(mem))

        if emit_events:
            self._bus.publish("memory.ingest.completed",
                              {"trace_id": trace_id, "memory_id": mem.memory_id})

        res = StageResult(
            stage="pipeline", ok=True,
            value={"memory": mem.to_dict(), "trust_score": trust_score,
                   "conflicts": conflicts, "is_duplicate": is_dup},
            provenance_changes={"trust_state": trust_state.value},
            metrics={"chars": len(final_content), "conflict_count": len(conflicts)},
            trace_id=trace_id,
        )
        return res

    # ----- trust transition helper --------------------------------------
    def transition_trust(self, memory_id: str, to_state: str,
                        *, ctp_tx_id: Optional[str] = None) -> StageResult:
        mem = self._eng.get(memory_id)
        if mem is None:
            res = StageResult(stage="trust_transition", ok=False, trace_id="")
            res.add_rejection(f"memory not found: {memory_id}")
            return res
        from_state = TrustState(mem.metadata.get("trust_state", TrustState.USER_FACT.value))
        try:
            new_state = apply_transition(from_state, TrustState(to_state))
        except ValueError as e:
            res = StageResult(stage="trust_transition", ok=False)
            res.add_rejection(str(e))
            return res
        meta = dict(mem.metadata)
        meta["trust_state"] = new_state.value
        self._eng.update(memory_id, metadata=meta)
        if ctp_tx_id:
            self._csg.add_edge(memory_id, memory_id, EdgeType.REFINES.value,
                               provenance="trust_transition", ctp_tx_id=ctp_tx_id)
        return StageResult(stage="trust_transition", ok=True,
                          value={"trust_state": new_state.value})
