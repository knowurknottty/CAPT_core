"""Canonical DREAM — consolidation as learning (Layer 3 / Learning).

Per Phase 3I, DREAM is offline consolidation that turns recent raw/consolidating
engrams and episodes into durable, verified knowledge. This is a CLEAN
implementation in CAPT_core (external ecosystem source NOT copied; licensing gate
[L] avoided).

Design: a DreamConsolidator takes engrams in RAW/CONSOLIDATING state, consolidates
them (engram lifecycle), and for those with corroborating evidence produces
SUPPORTED knowledge items (never silently VERIFIED — verification still requires
corroborating evidence per Phase 3G / I-02). Deterministic, auditable, local.
No network, no hidden state.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from capt_solo.knowledge.evidence import EvidenceStore, VerificationStatus
from capt_solo.knowledge.knowledge import KnowledgeStore, KnowledgeStatus
from capt_solo.memory.engram import ConsolidationState, EngramStore
from capt_solo.memory.types import MemoryType, MemoryRecord, validate_memory_record


@dataclass
class DreamSession:
    session_id: str
    processed: int
    consolidated: int
    knowledge_created: int
    started_at: float
    finished_at: Optional[float] = None
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__


class DreamConsolidator:
    """Offline consolidation: engrams/episodes -> durable knowledge."""

    def __init__(self, *,
                 engram_store: Optional[EngramStore] = None,
                 knowledge_store: Optional[KnowledgeStore] = None,
                 evidence_store: Optional[EvidenceStore] = None,
                 db_path: Optional[Any] = None) -> None:
        self._engram = engram_store or EngramStore(db_path=db_path)
        self._evidence = evidence_store or EvidenceStore(engine=self._engram._eng)
        self._knowledge = knowledge_store or KnowledgeStore(
            engine=self._engram._eng, evidence_store=self._evidence)

    def run(self, *, limit: int = 100) -> DreamSession:
        sess = DreamSession(
            session_id=uuid.uuid4().hex, processed=0, consolidated=0,
            knowledge_created=0, started_at=time.time(), notes=[])
        candidates = self._engram.list_engrams(
            state=ConsolidationState.RAW.value, limit=limit)
        candidates += self._engram.list_engrams(
            state=ConsolidationState.CONSOLIDATING.value, limit=limit)
        seen = set()
        for e in candidates:
            if e.engram_id in seen:
                continue
            seen.add(e.engram_id)
            sess.processed += 1
            # consolidate the engram (explicit lifecycle transition)
            self._engram.consolidate(e.engram_id)
            sess.consolidated += 1
            # produce knowledge only when there is corroborating evidence
            evs = [self._evidence.get_evidence(ev) for ev in e.source_evidence]
            evs = [v for v in evs if v is not None]
            corroborated = any(
                v.status in (VerificationStatus.CORROBORATED.value,
                             VerificationStatus.VERIFIED.value) for v in evs)
            if corroborated:
                item = self._knowledge.add_knowledge(
                    statement=e.content,
                    evidence_refs=list(e.source_evidence),
                    status=KnowledgeStatus.SUPPORTED.value,
                    confidence=e.confidence,
                    provenance="dream_consolidation")
                sess.knowledge_created += 1
                sess.notes.append(
                    f"engram {e.engram_id} -> knowledge {item.knowledge_id} (supported)")
            else:
                sess.notes.append(
                    f"engram {e.engram_id} consolidated; no corroborating evidence, "
                    f"withheld from knowledge (I-02)")
        sess.finished_at = time.time()
        return sess

    def last_session(self) -> Optional[DreamSession]:
        # sessions are returned to caller; persistence of session log is optional.
        # Kept simple: caller stores the returned session. This method is a hook
        # for future session-history storage.
        return None

    def propose_knowledge_record(self, engram: Any) -> MemoryRecord:
        """Return a proposed MemoryRecord for a consolidated engram.

        The proposed record is explicitly labeled is_inferred=True and is NOT
        written to canonical memory by this method — the caller decides whether
        (and how) to persist it. This enforces the boundary that DREAM-generated
        or recombined material must remain labeled as inferred/synthetic until
        verified, and must never silently overwrite canonical memory.
        """
        import uuid
        rec = MemoryRecord(
            record_id=f"dream-{uuid.uuid4().hex[:12]}",
            memory_type=MemoryType.INFERENCE,
            content=engram.content,
            provenance_chain=[f"engram:{engram.engram_id}", "dream_consolidation"],
            confidence=engram.confidence,
            source_refs=[engram.engram_id],
            evidence_refs=list(engram.source_evidence),
            is_inferred=True,
        )
        # Quarantine check: inferred records without provenance are flagged.
        validate_memory_record(rec)
        return rec
