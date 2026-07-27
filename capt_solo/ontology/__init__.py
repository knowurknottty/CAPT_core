"""CAPT shared ontology (Layer 0.5).

Per ADR-0002 and CAPT_CANON §4, the ontology is upstream of Memory, Knowledge,
Trust, and Governance. Those layers MUST consume these shared types rather than
defining incompatible duplicates (invariant I-12).

These are lightweight, serializable value types. They are deliberately free of
behavior so they can be reused across subsystems without coupling.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class OntologyTerm(str, Enum):
    """The 16 canonical ontology terms (CAPT_CANON §4)."""

    ENTITY = "entity"
    RELATIONSHIP = "relationship"
    IDENTITY = "identity"
    CLAIM = "claim"
    EVIDENCE = "evidence"
    PROVENANCE = "provenance"
    CONFIDENCE = "confidence"
    UNCERTAINTY = "uncertainty"
    TRUTH = "truth"
    CONTRADICTION = "contradiction"
    TEMPORAL_ORDERING = "temporal_ordering"
    OBSERVATION = "observation"
    INFERENCE = "inference"
    PROCEDURE = "procedure"
    SKILL = "skill"
    MEMORY = "memory"


@dataclass
class Entity:
    """An identifiable thing in the world or system (ontology: entity)."""

    entity_id: str
    entity_type: str
    label: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Relationship:
    """A typed link between two entities (ontology: relationship)."""

    source: str
    target: str
    relation: str
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Identity:
    """Stable identity of a subject/agent (ontology: identity)."""

    identity_id: str
    display_name: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Evidence:
    """A piece of evidence supporting or refuting a claim (ontology: evidence)."""

    evidence_id: str
    kind: str  # e.g. "observation", "document", "measurement"
    payload: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None


@dataclass
class Provenance:
    """Origin and derivation chain of a record (ontology: provenance)."""

    source: str
    method: Optional[str] = None
    upstream: List[str] = field(default_factory=list)
    recorded_at: Optional[float] = None
    actor: Optional[str] = None


@dataclass
class Confidence:
    """A graded belief, never a bare boolean (ontology: confidence/uncertainty)."""

    value: float  # 0.0 .. 1.0
    basis: Optional[str] = None  # why this confidence
    uncertainty: Optional[float] = None  # explicit residual uncertainty

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(f"confidence out of range: {self.value}")


@dataclass
class Claim:
    """An assertion that may be true, false, or unresolved (ontology: claim)."""

    claim_id: str
    statement: str
    status: str = "unresolved"  # unresolved | supported | refuted | contested
    confidence: Optional[Confidence] = None


@dataclass
class Contradiction:
    """A recorded conflict between two claims/records (ontology: contradiction)."""

    contradiction_id: str
    a: str
    b: str
    resolved: bool = False
    resolution: Optional[str] = None


@dataclass
class TemporalOrdering:
    """Explicit ordering of events (ontology: temporal_ordering)."""

    event_id: str
    timestamp: float
    sequence: Optional[int] = None
    precedes: List[str] = field(default_factory=list)


@dataclass
class Observation:
    """A direct perception/measurement (ontology: observation)."""

    observation_id: str
    content: str
    evidence: Optional[Evidence] = None


@dataclass
class Inference:
    """A derived conclusion, distinct from observation (ontology: inference)."""

    inference_id: str
    conclusion: str
    from_evidence: List[str] = field(default_factory=list)
    confidence: Optional[Confidence] = None


@dataclass
class Procedure:
    """A repeatable process (ontology: procedure)."""

    procedure_id: str
    name: str
    steps: List[str] = field(default_factory=list)


@dataclass
class Skill:
    """A capability that can be invoked (ontology: skill)."""

    skill_id: str
    name: str
    trigger: str = ""
    purpose: str = ""


@dataclass
class MemoryRef:
    """A reference to a memory record (ontology: memory)."""

    memory_id: str
    namespace: str


# Convenience: the canonical set of term names, for validation/registry use.
ONTOLOGY_TERMS: List[str] = [t.value for t in OntologyTerm]


def is_valid_term(name: str) -> bool:
    return name in ONTOLOGY_TERMS
