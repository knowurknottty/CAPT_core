"""Canonical Continuous Learning foundation (Layer 3 / Learning).

Per Phase 3J, continuous learning is the loop that turns verified outcomes and
feedback into durable strategy updates. This is a CLEAN canonical implementation
in CAPT_core building on the Knowledge/Evidence (3G) and DREAM (3I) foundations.

Design principles (CANON):
- Local, auditable, bounded (I-07). No hidden network, no silent state change.
- Evidence before assertion (I-02): a learning update never promotes a claim to
  VERIFIED without corroborating evidence; it adjusts confidence/strategy within
  explicit bounds.
- Drift detection: contradictions between new observations and existing knowledge
  are recorded, not silently overwritten.
- Every learning event is logged with provenance and timestamp.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from capt_solo.core.errors import MemoryError_
from capt_solo.knowledge.evidence import EvidenceStore, VerificationStatus
from capt_solo.knowledge.knowledge import KnowledgeStore, KnowledgeStatus
from capt_solo.memory.engine import MemoryEngine


class FeedbackKind(str, Enum):
    CORRECT = "correct"
    INCORRECT = "incorrect"
    PARTIAL = "partial"
    CONTRADICTION = "contradiction"


@dataclass
class LearningEvent:
    event_id: str
    knowledge_id: Optional[str]
    feedback: str
    delta_confidence: float
    note: str
    created_at: float = field(default_factory=time.time)
    provenance: str = "learning_loop"

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__


class ContinuousLearner:
    """Canonical continuous-learning loop over knowledge + evidence."""

    NAMESPACE = "learning_event"

    def __init__(self, *,
                 knowledge_store: Optional[KnowledgeStore] = None,
                 evidence_store: Optional[EvidenceStore] = None,
                 engine: Optional[MemoryEngine] = None,
                 db_path: Optional[Any] = None) -> None:
        # derive the shared engine from provided stores when available
        if engine is None:
            if knowledge_store is not None:
                engine = knowledge_store._eng
            elif evidence_store is not None:
                engine = evidence_store._eng
        self._eng = engine or MemoryEngine(db_path=db_path)
        self._evidence = evidence_store or EvidenceStore(engine=self._eng)
        self._knowledge = knowledge_store or KnowledgeStore(
            engine=self._eng, evidence_store=self._evidence)
        self._events: List[LearningEvent] = []

    def ingest_feedback(
        self, *,
        knowledge_id: str,
        feedback: str,
        note: str = "",
        provenance: str = "learning_loop",
        max_delta: float = 0.2,
    ) -> LearningEvent:
        if feedback not in (f.value for f in FeedbackKind):
            raise MemoryError_(f"invalid feedback kind: {feedback}")
        item = self._knowledge.get_knowledge(knowledge_id)
        if item is None:
            raise MemoryError_(f"knowledge not found: {knowledge_id}")
        # bounded confidence adjustment (I-07)
        if feedback == FeedbackKind.CORRECT.value:
            delta = max_delta
        elif feedback == FeedbackKind.INCORRECT.value:
            delta = -max_delta
        elif feedback == FeedbackKind.PARTIAL.value:
            delta = max_delta / 2.0
        else:  # contradiction -> flag, do not auto-demote below hypothesis bounds
            delta = -max_delta / 2.0
        new_conf = max(0.0, min(1.0, item.confidence + delta))
        item.confidence = round(new_conf, 4)
        # contradiction feedback may downgrade status but never silently verify
        if feedback == FeedbackKind.CONTRADICTION.value and \
                item.status == KnowledgeStatus.VERIFIED.value:
            item.status = KnowledgeStatus.CONTRADICTED.value
        self._knowledge._eng.update(
            knowledge_id, confidence=item.confidence,
            metadata={"knowledge": item.to_dict()},
            tags=["knowledge", item.status])
        ev = LearningEvent(
            event_id=uuid.uuid4().hex,
            knowledge_id=knowledge_id,
            feedback=feedback,
            delta_confidence=delta,
            note=note or f"confidence -> {item.confidence}",
            provenance=provenance,
        )
        self._events.append(ev)
        self._eng.store(
            json.dumps({"feedback": feedback, "knowledge_id": knowledge_id}),
            memory_id=ev.event_id,
            namespace=self.NAMESPACE,
            tier="learning",
            provenance=provenance,
            confidence=abs(delta),
            metadata={"learning_event": ev.to_dict()},
            tags=["learning", feedback],
        )
        return ev

    def detect_drift(self, knowledge_id: str) -> List[LearningEvent]:
        """Return learning events that contradicted this knowledge item."""
        return [e for e in self._events
                if e.knowledge_id == knowledge_id
                and e.feedback == FeedbackKind.CONTRADICTION.value]

    def learning_log(self, *, knowledge_id: Optional[str] = None) -> List[LearningEvent]:
        rows = self._eng.list(namespace=self.NAMESPACE, limit=1000)
        out = []
        for m in rows:
            if not m.metadata.get("learning_event"):
                continue
            d = m.metadata["learning_event"]
            e = LearningEvent(
                event_id=d["event_id"], knowledge_id=d.get("knowledge_id"),
                feedback=d["feedback"], delta_confidence=d["delta_confidence"],
                note=d.get("note", ""), created_at=d.get("created_at", m.created_at),
                provenance=d.get("provenance", "learning_loop"))
            if knowledge_id and e.knowledge_id != knowledge_id:
                continue
            out.append(e)
        return out

    def run_cycle(self, *, limit: int = 100) -> Dict[str, Any]:
        """Lightweight learning cycle: consolidate via DREAM then summarize.

        Delegates consolidation to the DreamConsolidator (3I) and reports counts.
        Kept explicit/auditable; no hidden behavior.
        """
        from capt_solo.learning.dream import DreamConsolidator
        dc = DreamConsolidator(
            engram_store=None, evidence_store=self._evidence,
            knowledge_store=self._knowledge, db_path=None)
        # share this learner's engine so engrams/knowledge are co-located
        from capt_solo.memory.engram import EngramStore
        dc._engram = EngramStore(engine=self._eng)
        sess = dc.run(limit=limit)
        return {
            "dream_processed": sess.processed,
            "dream_consolidated": sess.consolidated,
            "dream_knowledge_created": sess.knowledge_created,
            "learning_events": len(self._events),
        }
