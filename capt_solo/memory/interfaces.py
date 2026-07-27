"""Canonical memory interfaces (Layer 3).

These define the permanent architectural contracts for CAPT memory, reusing the
shared ontology types from :mod:`capt_solo.ontology` (ADR-0002, I-12). They are
the *canonical definition*; the current implementation (:class:`MemoryEngine`)
satisfies a subset and is extended toward these contracts in Phase 3C.

No parallel incompatible definitions are introduced in individual memory modules
(I-12). All memory subsystems import these types.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol

from capt_solo.ontology import (
    Confidence,
    Evidence,
    Identity,
    Provenance,
    TemporalOrdering,
)


class RetentionPolicy(str, Enum):
    """Canonical retention semantics for a memory record."""

    TRANSIENT = "transient"      # cleared on session end
    SESSION = "session"          # persists for the session
    DURABLE = "durable"          # persists until explicitly deleted
    ARCHIVAL = "archival"        # long-term, rarely mutated
    TOMBSTONE = "tombstone"      # deleted but retained as a deletion marker


class ConsentState(str, Enum):
    """Local consent state for a memory operation (Phase 3E)."""

    GRANTED = "granted"
    DENIED = "denied"
    UNSET = "unset"              # default-deny for sensitive ops
    EXPIRED = "expired"


class MigrationDirection(str, Enum):
    FORWARD = "forward"
    ROLLBACK = "rollback"


@dataclass
class MemoryIdentity:
    """Canonical identity of a memory record (ontology: identity)."""

    memory_id: str
    namespace: str
    identity_link: Optional[str] = None  # linked subject/agent identity


@dataclass
class TemporalMetadata:
    """Canonical temporal metadata (ontology: temporal_ordering)."""

    created_at: float
    updated_at: float
    sequence: Optional[int] = None
    precedes: List[str] = field(default_factory=list)


@dataclass
class SourceEvidence:
    """Canonical source evidence linkage (ontology: evidence)."""

    evidence: Optional[Evidence] = None
    evidence_refs: List[str] = field(default_factory=list)


@dataclass
class MemoryRecord:
    """Canonical memory record — the single memory representation.

    Reuses ontology types for provenance, confidence, uncertainty, evidence,
    identity, and temporal ordering. This is the contract all memory subsystems
    converge on (I-12). The current :class:`MemoryEngine` record is an earlier
    shape; an adapter maps between them.
    """

    memory_id: str
    content: str
    namespace: str
    provenance: Provenance
    confidence: Confidence
    temporal: TemporalMetadata
    identity: MemoryIdentity
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    uncertainty: Optional[float] = None       # explicit residual uncertainty
    source_evidence: SourceEvidence = field(default_factory=SourceEvidence)
    retention: RetentionPolicy = RetentionPolicy.DURABLE
    consent: ConsentState = ConsentState.UNSET
    lifecycle_state: str = "active"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "content": self.content,
            "namespace": self.namespace,
            "provenance": self.provenance.__dict__,
            "confidence": self.confidence.__dict__,
            "uncertainty": self.uncertainty,
            "temporal": self.temporal.__dict__,
            "identity": self.identity.__dict__,
            "tags": self.tags,
            "metadata": self.metadata,
            "source_evidence": self.source_evidence.__dict__,
            "retention": self.retention.value,
            "consent": self.consent.value,
            "lifecycle_state": self.lifecycle_state,
        }


@dataclass
class RetrievalResult:
    """Result of a memory retrieval, carrying provenance and uncertainty."""

    records: List[MemoryRecord]
    query: str
    truncated: bool = False
    reason: Optional[str] = None


@dataclass
class ReplayEvent:
    """A single replayable event (Phase 3E)."""

    event_id: str
    kind: str
    payload: Dict[str, Any]
    timestamp: float
    provenance: Optional[Provenance] = None
    replay_version: int = 1


@dataclass
class MigrationVersion:
    """A schema/record migration version marker."""

    version: int
    direction: MigrationDirection = MigrationDirection.FORWARD
    applied_at: Optional[float] = None
    receipt: Optional[Dict[str, Any]] = None


class MemoryStore(Protocol):
    """Canonical memory store contract (subset; extended by implementations)."""

    def store(self, record: MemoryRecord) -> str: ...
    def get(self, memory_id: str) -> Optional[MemoryRecord]: ...
    def delete(self, memory_id: str) -> bool: ...
    def search(self, query: str, *, limit: int = 20) -> RetrievalResult: ...
    def export(self) -> Dict[str, Any]: ...
    def import_records(self, data: Dict[str, Any]) -> int: ...


def memory_to_canonical(m: "Any") -> MemoryRecord:
    """Adapt a :class:`capt_solo.memory.engine.Memory` to a canonical MemoryRecord.

    Reuses ontology types for provenance/confidence/uncertainty/identity/temporal.
    This is the single mapping point (I-12) — no other module redefines it.
    """
    from capt_solo.ontology import Confidence, Provenance

    return MemoryRecord(
        memory_id=m.memory_id,
        content=m.content,
        namespace=m.namespace,
        provenance=Provenance(source=m.provenance),
        confidence=Confidence(value=m.confidence),
        uncertainty=m.uncertainty,
        temporal=TemporalMetadata(created_at=m.created_at, updated_at=m.updated_at),
        identity=MemoryIdentity(
            memory_id=m.memory_id, namespace=m.namespace, identity_link=m.identity_link),
        tags=list(m.tags),
        metadata=dict(m.metadata),
        source_evidence=SourceEvidence(evidence_refs=list(m.evidence_refs)),
        retention=RetentionPolicy(m.retention) if m.retention in (p.value for p in RetentionPolicy) else RetentionPolicy.DURABLE,
        consent=ConsentState(m.consent) if m.consent in (c.value for c in ConsentState) else ConsentState.UNSET,
        lifecycle_state=m.lifecycle_state,
    )


def canonical_to_memory_kwargs(rec: MemoryRecord) -> Dict[str, Any]:
    """Adapt a canonical MemoryRecord back to MemoryEngine.store kwargs."""
    return {
        "content": rec.content,
        "namespace": rec.namespace,
        "provenance": rec.provenance.source,
        "confidence": rec.confidence.value,
        "uncertainty": rec.uncertainty,
        "metadata": rec.metadata,
        "tags": rec.tags,
        "retention": rec.retention.value,
        "consent": rec.consent.value,
        "identity_link": rec.identity.identity_link,
        "evidence_refs": list(rec.source_evidence.evidence_refs),
    }
