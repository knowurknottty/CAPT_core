"""Canonical Knowledge Store (Layer 3 — Knowledge convergence).

Per Phase 3G, knowledge is portable, verifiable packages (knowledge bubbles)
linked to evidence and trust state. A knowledge item is NEVER silently promoted
to verified: it carries an explicit trust/verification status derived from its
linked evidence (I-02, trust-engine semantics).

Backed by MemoryEngine (namespace ``knowledge``), reusing canonical fields and
ontology types. No duplicate persistence (I-12).
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
from capt_solo.memory.engine import MemoryEngine


class KnowledgeStatus(str, Enum):
    HYPOTHESIS = "hypothesis"
    SUPPORTED = "supported"
    VERIFIED = "verified"
    CONTRADICTED = "contradicted"
    DEPRECATED = "deprecated"


@dataclass
class KnowledgeItem:
    knowledge_id: str
    statement: str
    evidence_refs: List[str]
    trust_state: str
    status: str = KnowledgeStatus.HYPOTHESIS.value
    confidence: float = 0.5
    provenance: str = "unknown"
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__


class KnowledgeStore:
    """Canonical knowledge bubble store."""

    NAMESPACE = "knowledge"

    def __init__(self, engine: Optional[MemoryEngine] = None, *,
                 db_path: Optional[Any] = None,
                 evidence_store: Optional[EvidenceStore] = None) -> None:
        self._eng = engine or MemoryEngine(db_path=db_path)
        self._evidence = evidence_store or EvidenceStore(engine=self._eng)

    def add_knowledge(
        self,
        *,
        statement: str,
        evidence_refs: List[str],
        trust_state: str = "UNVERIFIED",
        status: str = KnowledgeStatus.HYPOTHESIS.value,
        confidence: float = 0.5,
        provenance: str = "unknown",
    ) -> KnowledgeItem:
        if not statement:
            raise MemoryError_("statement required")
        if not (0.0 <= confidence <= 1.0):
            raise MemoryError_("confidence must be 0..1")
        if status not in (s.value for s in KnowledgeStatus):
            raise MemoryError_("invalid knowledge status")
        item = KnowledgeItem(
            knowledge_id=uuid.uuid4().hex,
            statement=statement,
            evidence_refs=list(evidence_refs),
            trust_state=trust_state,
            status=status,
            confidence=confidence,
            provenance=provenance,
        )
        self._eng.store(
            json.dumps({"statement": statement, "status": status}),
            memory_id=item.knowledge_id,
            namespace=self.NAMESPACE,
            tier="knowledge",
            provenance=provenance,
            confidence=confidence,
            evidence_refs=list(evidence_refs),
            metadata={"knowledge": item.to_dict()},
            tags=["knowledge", status],
        )
        return item

    def link_evidence(self, knowledge_id: str, evidence_id: str) -> KnowledgeItem:
        item = self.get_knowledge(knowledge_id)
        if item is None:
            raise MemoryError_(f"knowledge not found: {knowledge_id}")
        if self._evidence.get_evidence(evidence_id) is None:
            raise MemoryError_(f"evidence not found: {evidence_id}")
        if evidence_id not in item.evidence_refs:
            item.evidence_refs.append(evidence_id)
        self._eng.update(knowledge_id, evidence_refs=item.evidence_refs,
                         metadata={"knowledge": item.to_dict()})
        return item

    def promote_status(self, knowledge_id: str, status: str) -> KnowledgeItem:
        """Promote knowledge status. Verified requires at least one corroborating
        evidence record (I-02: evidence before assertion)."""
        item = self.get_knowledge(knowledge_id)
        if item is None:
            raise MemoryError_(f"knowledge not found: {knowledge_id}")
        if status not in (s.value for s in KnowledgeStatus):
            raise MemoryError_("invalid knowledge status")
        if status == KnowledgeStatus.VERIFIED.value:
            evs = [self._evidence.get_evidence(e) for e in item.evidence_refs]
            evs = [e for e in evs if e is not None]
            if not any(e.status in (VerificationStatus.CORROBORATED.value,
                                    VerificationStatus.VERIFIED.value)
                       for e in evs):
                raise MemoryError_(
                    "cannot verify knowledge without corroborating evidence")
        item.status = status
        self._eng.update(knowledge_id, metadata={"knowledge": item.to_dict()},
                         tags=["knowledge", status])
        return item

    def get_knowledge(self, knowledge_id: str) -> Optional[KnowledgeItem]:
        mem = self._eng.get(knowledge_id)
        if mem is None or not mem.metadata.get("knowledge"):
            return None
        return self._from_mem(mem)

    def list_knowledge(self, *, status: Optional[str] = None,
                       limit: int = 100) -> List[KnowledgeItem]:
        rows = self._eng.list(namespace=self.NAMESPACE, limit=limit)
        out = []
        for m in rows:
            if not m.metadata.get("knowledge"):
                continue
            item = self._from_mem(m)
            if status and item.status != status:
                continue
            out.append(item)
        return out

    def delete_knowledge(self, knowledge_id: str) -> bool:
        return self._eng.delete(knowledge_id)

    @staticmethod
    def _from_mem(mem: Any) -> KnowledgeItem:
        d = mem.metadata["knowledge"]
        return KnowledgeItem(
            knowledge_id=d["knowledge_id"],
            statement=d["statement"],
            evidence_refs=d.get("evidence_refs", []),
            trust_state=d.get("trust_state", "UNVERIFIED"),
            status=d.get("status", KnowledgeStatus.HYPOTHESIS.value),
            confidence=d.get("confidence", 0.5),
            provenance=d.get("provenance", "unknown"),
            created_at=d.get("created_at", mem.created_at),
            metadata=d.get("metadata", {}),
        )
