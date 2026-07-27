"""CAPT memory-type taxonomy and canonical MemoryRecord (Layer 3 convergence).

Implements the owner-approved explicit memory-type distinctions (Decision 2):
Event, Observation, Episode, Interpretation, Inference, Belief, Identity Narrative,
Autobiographical Memory, Semantic Memory, Revision, Correction, Supersession,
Provenance, Replay metadata.

Provides:
- MemoryType enum (canonical, explicit — no collapse into one generic record).
- MemoryRecord dataclass with provenance chain, non-destructive revision history,
  correction/supersession links, uncertainty, and a quarantine flag.
- validate_memory_record(): quarantines malformed data instead of silently storing.
- Non-destructive revision: revisions are appended; the canonical content is never
  overwritten in place.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class MemoryType(Enum):
    """Explicit memory-type distinctions. Do not collapse into one generic type."""
    EVENT = "event"                       # something that happened (raw occurrence)
    OBSERVATION = "observation"           # a perceived fact (sensed/measured)
    EPISODE = "episode"                   # a bounded sequence of events/observations
    INTERPRETATION = "interpretation"     # meaning assigned to observations
    INFERENCE = "inference"               # derived from premises (logic/statistics)
    BELIEF = "belief"                     # held conviction (may be uncertain)
    IDENTITY_NARRATIVE = "identity_narrative"  # self-model / agent identity story
    AUTOBIOGRAPHICAL = "autobiographical" # personal history of the agent
    SEMANTIC = "semantic"                 # general factual knowledge (decontextualized)
    REVISION = "revision"                 # a non-destructive edit of a prior record
    CORRECTION = "correction"             # explicit fix of an error in a prior record
    SUPERSESSION = "supersession"         # a later record that replaces an earlier one
    PROVENANCE = "provenance"             # metadata about origin/derivation chain
    REPLAY = "replay"                     # replay of a prior memory (audit/learning)


class QuarantineReason(Enum):
    EMPTY_CONTENT = "empty_content"
    INVALID_TYPE = "invalid_type"
    MISSING_PROVENANCE = "missing_provenance"
    MALFORMED_JSON = "malformed_json"
    UNCERTAIN_WITHOUT_BOUNDS = "uncertainty_without_bounds"


@dataclass
class RevisionEntry:
    revision_id: str
    prior_content_hash: str
    new_content_hash: str
    kind: str  # "revision" | "correction" | "supersession"
    timestamp: float
    actor: str = "system"
    note: str = ""


@dataclass
class MemoryRecord:
    """Canonical memory record with explicit type and full provenance.

    Non-destructive: content is immutable once set; changes create RevisionEntry
    objects and optionally a new record (supersession) rather than mutating this
    record's canonical content.
    """
    record_id: str
    memory_type: MemoryType
    content: str
    provenance_chain: List[str] = field(default_factory=list)
    uncertainty: Optional[float] = None
    confidence: float = 1.0
    source_refs: List[str] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)
    revisions: List[RevisionEntry] = field(default_factory=list)
    supersedes: Optional[str] = None
    superseded_by: Optional[str] = None
    is_correction: bool = False
    is_inferred: bool = False
    is_synthetic: bool = False
    quarantined: bool = False
    quarantine_reason: Optional[str] = None
    replay_metadata: Dict[str, str] = field(default_factory=dict)
    created_at: float = field(default_factory=lambda: __import__("time").time())

    def content_hash(self) -> str:
        import hashlib
        return hashlib.sha256(self.content.encode()).hexdigest()[:16]

    def apply_revision(self, *, new_content: str, kind: str, actor: str = "system",
                       note: str = "") -> RevisionEntry:
        """Record a non-destructive revision. Does NOT mutate this record's
        canonical content; returns the RevisionEntry for the caller to link."""
        if kind not in ("revision", "correction", "supersession"):
            raise ValueError(f"invalid revision kind: {kind!r}")
        import time
        rev = RevisionEntry(
            revision_id=f"rev-{len(self.revisions) + 1}",
            prior_content_hash=self.content_hash(),
            new_content_hash=hashlib_sha256(new_content),
            kind=kind, timestamp=time.time(), actor=actor, note=note)
        self.revisions.append(rev)
        if kind == "correction":
            self.is_correction = True
        return rev

    def to_dict(self) -> Dict:
        return {
            "record_id": self.record_id,
            "memory_type": self.memory_type.value,
            "content": self.content,
            "provenance_chain": self.provenance_chain,
            "uncertainty": self.uncertainty,
            "confidence": self.confidence,
            "source_refs": self.source_refs,
            "evidence_refs": self.evidence_refs,
            "revisions": [r.__dict__ for r in self.revisions],
            "supersedes": self.supersedes,
            "superseded_by": self.superseded_by,
            "is_correction": self.is_correction,
            "is_inferred": self.is_inferred,
            "is_synthetic": self.is_synthetic,
            "quarantined": self.quarantined,
            "quarantine_reason": self.quarantine_reason,
            "replay_metadata": self.replay_metadata,
            "created_at": self.created_at,
        }


def hashlib_sha256(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def validate_memory_record(rec: MemoryRecord) -> MemoryRecord:
    """Quarantine malformed data instead of silently storing it.

    Sets rec.quarantined=True and rec.quarantine_reason when invalid. Returns the
    (possibly mutated) record so callers can route quarantined records to a
    separate store rather than the canonical memory.
    """
    if not rec.content or not rec.content.strip():
        rec.quarantined = True
        rec.quarantine_reason = QuarantineReason.EMPTY_CONTENT.value
        return rec
    if not isinstance(rec.memory_type, MemoryType):
        rec.quarantined = True
        rec.quarantine_reason = QuarantineReason.INVALID_TYPE.value
        return rec
    if rec.uncertainty is not None and not (0.0 <= rec.uncertainty <= 1.0):
        rec.quarantined = True
        rec.quarantine_reason = QuarantineReason.UNCERTAIN_WITHOUT_BOUNDS.value
        return rec
    # Provenance is required for inferred/synthetic records (no silent fabrication)
    if (rec.is_inferred or rec.is_synthetic) and not rec.provenance_chain:
        rec.quarantined = True
        rec.quarantine_reason = QuarantineReason.MISSING_PROVENANCE.value
        return rec
    return rec


def memory_type_from_string(s: str) -> MemoryType:
    for mt in MemoryType:
        if mt.value == s:
            return mt
    raise ValueError(f"unknown memory type: {s!r}")
