"""Canonical Evidence Store (Layer 3 — Knowledge/Evidence convergence).

Per Phase 3G, evidence is first-class. An evidence record links a claim to its
supporting source(s), provenance, confidence, and verification status. Evidence
is what promotes a claim toward verified status — never repetition or inference
alone (I-02 evidence before assertion; trust engine semantics).

Backed by MemoryEngine (namespace ``evidence``), reusing canonical fields and
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
from capt_solo.memory.engine import MemoryEngine
from capt_solo.ontology import Confidence, Evidence as EvidenceTerm, Provenance


class VerificationStatus(str, Enum):
    UNVERIFIED = "unverified"
    CORROBORATED = "corroborated"
    CONTRADICTED = "contradicted"
    VERIFIED = "verified"


@dataclass
class EvidenceRecord:
    evidence_id: str
    claim: str
    source_refs: List[str]
    provenance: str
    confidence: float
    status: str = VerificationStatus.UNVERIFIED.value
    contradicts: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__


class EvidenceStore:
    """Canonical evidence ledger."""

    NAMESPACE = "evidence"

    def __init__(self, engine: Optional[MemoryEngine] = None, *,
                 db_path: Optional[Any] = None) -> None:
        self._eng = engine or MemoryEngine(db_path=db_path)

    def add_evidence(
        self,
        *,
        claim: str,
        source_refs: List[str],
        provenance: str = "unknown",
        confidence: float = 1.0,
        status: str = VerificationStatus.UNVERIFIED.value,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EvidenceRecord:
        if not claim:
            raise MemoryError_("claim required")
        if not (0.0 <= confidence <= 1.0):
            raise MemoryError_("confidence must be 0..1")
        if status not in (s.value for s in VerificationStatus):
            raise MemoryError_("invalid verification status")
        rec = EvidenceRecord(
            evidence_id=uuid.uuid4().hex,
            claim=claim,
            source_refs=list(source_refs),
            provenance=provenance,
            confidence=confidence,
            status=status,
            metadata=metadata or {},
        )
        self._eng.store(
            json.dumps({"claim": claim, "status": status}),
            memory_id=rec.evidence_id,
            namespace=self.NAMESPACE,
            tier="evidence",
            provenance=provenance,
            confidence=confidence,
            evidence_refs=list(source_refs),
            metadata={"evidence": rec.to_dict()},
            tags=["evidence", status],
        )
        return rec

    def set_status(self, evidence_id: str, status: str) -> EvidenceRecord:
        rec = self.get_evidence(evidence_id)
        if rec is None:
            raise MemoryError_(f"evidence not found: {evidence_id}")
        if status not in (s.value for s in VerificationStatus):
            raise MemoryError_(("invalid verification status"))
        rec.status = status
        self._eng.update(evidence_id, metadata={"evidence": rec.to_dict()},
                         tags=["evidence", status])
        return rec

    def mark_contradiction(self, evidence_id: str, other_id: str) -> None:
        a = self.get_evidence(evidence_id)
        b = self.get_evidence(other_id)
        if a is None or b is None:
            raise MemoryError_("both evidence records must exist")
        if other_id not in a.contradicts:
            a.contradicts.append(other_id)
        if evidence_id not in b.contradicts:
            b.contradicts.append(evidence_id)
        self._eng.update(evidence_id, metadata={"evidence": a.to_dict()})
        self._eng.update(other_id, metadata={"evidence": b.to_dict()})

    def get_evidence(self, evidence_id: str) -> Optional[EvidenceRecord]:
        mem = self._eng.get(evidence_id)
        if mem is None or not mem.metadata.get("evidence"):
            return None
        return self._from_mem(mem)

    def list_evidence(self, *, status: Optional[str] = None,
                      claim_contains: Optional[str] = None,
                      limit: int = 100) -> List[EvidenceRecord]:
        rows = self._eng.list(namespace=self.NAMESPACE, limit=limit)
        out = []
        for m in rows:
            if not m.metadata.get("evidence"):
                continue
            rec = self._from_mem(m)
            if status and rec.status != status:
                continue
            if claim_contains and claim_contains not in rec.claim:
                continue
            out.append(rec)
        return out

    def delete_evidence(self, evidence_id: str) -> bool:
        return self._eng.delete(evidence_id)

    @staticmethod
    def _from_mem(mem: Any) -> EvidenceRecord:
        d = mem.metadata["evidence"]
        return EvidenceRecord(
            evidence_id=d["evidence_id"],
            claim=d["claim"],
            source_refs=d.get("source_refs", []),
            provenance=d.get("provenance", "unknown"),
            confidence=d.get("confidence", 1.0),
            status=d.get("status", VerificationStatus.UNVERIFIED.value),
            contradicts=d.get("contradicts", []),
            created_at=d.get("created_at", mem.created_at),
            metadata=d.get("metadata", {}),
        )

    # ontology bridge (I-12 single mapping)
    def to_ontology(self, evidence_id: str) -> Optional[EvidenceTerm]:
        rec = self.get_evidence(evidence_id)
        if rec is None:
            return None
        return EvidenceTerm(
            evidence_id=rec.evidence_id,
            kind="evidence_record",
            payload={
                "claim": rec.claim,
                "source_refs": rec.source_refs,
                "status": rec.status,
                "confidence": rec.confidence,
            },
            source=rec.provenance,
        )
