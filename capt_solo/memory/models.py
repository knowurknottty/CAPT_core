"""CAPT Solo v0.2 — shared models and typed pipeline results.

This module defines the public enums and dataclasses used across the memory
processing pipeline, CSG graph, AntiToken, and context builder. Every pipeline
stage returns a typed ``StageResult`` so failures are explicit and never leave
partially committed state.

All types here are stable public surface for v0.2.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------
class MemoryKind(str, enum.Enum):
    """Node/memory types for CSG and AntiToken classification."""

    FACT = "fact"
    CLAIM = "claim"
    DECISION = "decision"
    PROCEDURE = "procedure"
    OBSERVATION = "observation"
    HYPOTHESIS = "hypothesis"
    REQUIREMENT = "requirement"
    CONSTRAINT = "constraint"
    FAILURE = "failure"
    LESSON = "lesson"
    TASK = "task"
    ARTIFACT_REF = "artifact_reference"
    TRANSACTION_REF = "transaction_reference"
    SESSION_SUMMARY = "session_summary"

    @classmethod
    def from_tag(cls, value: str) -> "MemoryKind":
        try:
            return cls(value)
        except ValueError:
            return cls.FACT


class EdgeType(str, enum.Enum):
    """Allowed CSG edge types."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    SUPERSEDES = "supersedes"
    DERIVES_FROM = "derives-from"
    CAUSED_BY = "caused-by"
    RESOLVES = "resolves"
    DEPENDS_ON = "depends-on"
    RELATES_TO = "relates-to"
    PRODUCED_BY = "produced-by"
    VERIFIED_BY = "verified-by"
    INVALIDATES = "invalidates"
    DUPLICATES = "duplicates"
    REFINES = "refines"

    @classmethod
    def values(cls) -> List[str]:
        return [e.value for e in cls]


class TrustState(str, enum.Enum):
    """Deterministic trust states. An inference is NEVER silently promoted to
    a verified fact."""

    USER_FACT = "user_provided_fact"
    OBSERVED_FACT = "observed_fact"
    TOOL_RESULT = "tool_result"
    VERIFIED_RESULT = "verified_result"
    INFERENCE = "inference"
    HYPOTHESIS = "hypothesis"
    PREFERENCE = "preference"
    INSTRUCTION = "instruction"
    GENERATED_SUMMARY = "generated_summary"
    CONFLICTED = "conflicted"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class SelectionStatus(str, enum.Enum):
    SELECTED = "selected"
    EXCLUDED = "excluded"
    PENALIZED = "penalized"


# --------------------------------------------------------------------------
# Pipeline stage result
# --------------------------------------------------------------------------
@dataclass
class StageResult:
    """Uniform return type for every pipeline stage.

    A failed stage must set ``ok=False`` and populate ``rejections``; the
    pipeline orchestrator must NOT persist anything when a stage fails.
    """

    stage: str
    ok: bool
    value: Any = None
    warnings: List[str] = field(default_factory=list)
    rejections: List[str] = field(default_factory=list)
    provenance_changes: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    trace_id: str = ""

    def add_warning(self, w: str) -> None:
        self.warnings.append(w)

    def add_rejection(self, r: str) -> None:
        self.rejections.append(r)
        self.ok = False


# --------------------------------------------------------------------------
# AntiToken packet
# --------------------------------------------------------------------------
@dataclass
class AntiTokenPacket:
    """Compact, decision-relevant representation of a memory.

    Fidelity fields (negation, uncertainty, contraindications, security
    warnings, unresolved conflicts, numeric/date/version/identifier values,
    evidence refs, destructive-action warnings) are preserved by the extractor
    and validated by :func:`AntiTokenExtractor.validate`.
    """

    memory_id: str
    kind: str
    assertion: str
    subject: str = ""
    action: str = ""
    obj: str = ""
    constraints: List[str] = field(default_factory=list)
    rationale: List[str] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)
    confidence: float = 1.0
    provenance_refs: List[str] = field(default_factory=list)
    temporal_scope: str = ""
    status: str = "active"
    contradictions: List[str] = field(default_factory=list)
    supersedes: List[str] = field(default_factory=list)
    unresolved_questions: List[str] = field(default_factory=list)
    ctp_refs: List[str] = field(default_factory=list)
    negation: bool = False
    uncertainty: bool = False
    security_warning: bool = False
    destructive_warning: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "kind": self.kind,
            "assertion": self.assertion,
            "subject": self.subject,
            "action": self.action,
            "obj": self.obj,
            "constraints": self.constraints,
            "rationale": self.rationale,
            "evidence_refs": self.evidence_refs,
            "confidence": self.confidence,
            "provenance_refs": self.provenance_refs,
            "temporal_scope": self.temporal_scope,
            "status": self.status,
            "contradictions": self.contradictions,
            "supersedes": self.supersedes,
            "unresolved_questions": self.unresolved_questions,
            "ctp_refs": self.ctp_refs,
            "negation": self.negation,
            "uncertainty": self.uncertainty,
            "security_warning": self.security_warning,
            "destructive_warning": self.destructive_warning,
        }


# --------------------------------------------------------------------------
# Context build result
# --------------------------------------------------------------------------
@dataclass
class ContextItem:
    memory_id: str
    score: float
    selected: bool
    reason: str
    antitoken: Optional[AntiTokenPacket] = None


@dataclass
class ContextBuildResult:
    query: str
    items: List[ContextItem]
    rendered: str
    exclusions: List[Dict[str, Any]]
    conflicts: List[Dict[str, Any]]
    warnings: List[str]
    estimated_source_chars: int
    estimated_compressed_chars: int
    reduction_ratio: float
    trace_id: str
    config_snapshot: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "items": [
                {
                    "memory_id": i.memory_id,
                    "score": i.score,
                    "selected": i.selected,
                    "reason": i.reason,
                    "antitoken": i.antitoken.to_dict() if i.antitoken else None,
                }
                for i in self.items
            ],
            "rendered": self.rendered,
            "exclusions": self.exclusions,
            "conflicts": self.conflicts,
            "warnings": self.warnings,
            "estimated_source_chars": self.estimated_source_chars,
            "estimated_compressed_chars": self.estimated_compressed_chars,
            "reduction_ratio": self.reduction_ratio,
            "trace_id": self.trace_id,
            "config_snapshot": self.config_snapshot,
        }
