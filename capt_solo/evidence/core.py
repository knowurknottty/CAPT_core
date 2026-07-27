"""Evidence Engine core — provenance-backed evidence records.

Distinguishes what is present / believed / inferred / attempted / changed /
verified / valid / invalidated / project-local / globally-reusable. These are
explicit fields and statuses, never collapsed into one generic flag.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class EvidenceClass(str, Enum):
    DIRECT_OBSERVATION = "direct_observation"
    TOOL_OUTPUT = "tool_output"
    TEST_RESULT = "test_result"
    BUILD_RESULT = "build_result"
    STATIC_ANALYSIS = "static_analysis"
    RUNTIME_OBSERVATION = "runtime_observation"
    SPECIFICATION = "specification"
    USER_DECISION = "user_decision"
    DERIVED_INFERENCE = "derived_inference"
    SIMULATION_RESULT = "simulation_result"
    EXTERNAL_REFERENCE = "external_reference"
    VERIFICATION = "verification"


class EvidenceStatus(str, Enum):
    CURRENT = "current"
    PARTIAL = "partial"
    SUPERSEDED = "superseded"
    INVALIDATED = "invalidated"
    QUARANTINED = "quarantined"
    EXPIRED = "expired"
    UNVERIFIED = "unverified"
    CONFLICTED = "conflicted"


class EvidenceScope(str, Enum):
    """Where evidence lives and how broadly it applies."""
    WORKSPACE = "workspace"          # project-local, ephemeral
    PROJECT = "project"              # project memory, namespaced
    GLOBAL = "global"                # cross-project, explicitly promoted


class EvidenceRelation(str, Enum):
    """How one evidence record relates to another or to a claim."""
    SUPPORTS = "supports"
    REFUTES = "refutes"
    EXTENDS = "extends"
    DEPENDS_ON = "depends_on"
    SUPERSEDES = "supersedes"
    CONTRADICTS = "contradicts"


class EvidenceSourceType(str, Enum):
    TEST = "test"
    BUILD = "build"
    STATIC_ANALYSIS = "static_analysis"
    RUNTIME = "runtime"
    USER = "user"
    DOCUMENT = "document"
    DERIVATION = "derivation"
    SIMULATION = "simulation"
    EXTERNAL = "external"


@dataclass
class EvidenceSource:
    source_type: str
    reference: str                    # file path, URL, record id, command
    repository: str = ""
    project_id: str = ""
    branch: str = ""
    head_commit: str = ""
    working_tree_state: str = ""
    source_paths: List[str] = field(default_factory=list)
    environment_identity: str = ""


@dataclass
class EvidenceClaim:
    """The proposition being supported (what is claimed / believed / inferred)."""
    claim_id: str
    statement: str
    claim_type: str = "behavior"     # behavior | property | safety | performance | compatibility | acceptance
    confidence_class: str = "observed"  # observed | believed | inferred | attempted | verified | invalidated


@dataclass
class EvidenceRecord:
    record_id: str
    claim: EvidenceClaim
    evidence_class: str
    source: EvidenceSource
    status: str = EvidenceStatus.UNVERIFIED.value
    confidence: float = 0.0
    verification_record_id: Optional[str] = None
    verification_scope: Optional[str] = None
    provenance_chain: List[str] = field(default_factory=list)
    parent_records: List[str] = field(default_factory=list)
    supersession_links: List[str] = field(default_factory=list)
    invalidation_links: List[str] = field(default_factory=list)
    ttl: Optional[str] = None        # only where explicitly appropriate
    summary: str = ""
    reason_codes: List[str] = field(default_factory=list)
    scope: str = EvidenceScope.PROJECT.value
    project_id: str = ""
    repository_identity: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "claim": self.claim.__dict__,
            "evidence_class": self.evidence_class,
            "source": self.source.__dict__,
            "verification_record_id": self.verification_record_id,
            "verification_scope": self.verification_scope,
            "status": self.status,
            "confidence": self.confidence,
            "provenance_chain": self.provenance_chain,
            "parent_records": self.parent_records,
            "supersession_links": self.supersession_links,
            "invalidation_links": self.invalidation_links,
            "ttl": self.ttl,
            "summary": self.summary,
            "reason_codes": self.reason_codes,
            "scope": self.scope,
            "created_at": self.created_at,
            "project_id": self.project_id,
            "repository_identity": self.repository_identity,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EvidenceRecord":
        claim = EvidenceClaim(**d["claim"])
        source = EvidenceSource(**d["source"])
        return cls(
            record_id=d["record_id"], claim=claim, evidence_class=d["evidence_class"],
            source=source, verification_record_id=d.get("verification_record_id"),
            verification_scope=d.get("verification_scope"), status=d.get("status", EvidenceStatus.UNVERIFIED.value),
            confidence=d.get("confidence", 0.0), provenance_chain=d.get("provenance_chain", []),
            parent_records=d.get("parent_records", []), supersession_links=d.get("supersession_links", []),
            invalidation_links=d.get("invalidation_links", []), ttl=d.get("ttl"),
            summary=d.get("summary", ""), reason_codes=d.get("reason_codes", []),
            scope=d.get("scope", EvidenceScope.PROJECT.value),
            created_at=d.get("created_at", ""), project_id=d.get("project_id", ""),
            repository_identity=d.get("repository_identity", ""),
        )


@dataclass
class EvidenceBundle:
    """A collection of evidence records supporting a set of claims."""
    bundle_id: str
    records: List[EvidenceRecord] = field(default_factory=list)

    def add(self, rec: EvidenceRecord) -> None:
        self.records.append(rec)

    def by_claim(self, claim_id: str) -> List[EvidenceRecord]:
        return [r for r in self.records if r.claim.claim_id == claim_id]

    def current_for_claim(self, claim_id: str) -> List[EvidenceRecord]:
        return [r for r in self.by_claim(claim_id) if r.status == EvidenceStatus.CURRENT.value]


@dataclass
class EvidenceQuery:
    claim_id: Optional[str] = None
    evidence_class: Optional[str] = None
    status: Optional[str] = None
    scope: Optional[str] = None
    project_id: Optional[str] = None
    verification_record_id: Optional[str] = None


@dataclass
class EvidenceDecision:
    """Structured decision a guard or engine can consume."""
    action: str                         # REUSE_CURRENT_EVIDENCE | RUN_TARGETED_VERIFICATION | ...
    state_identity: str                 # equivalent | changed | unknown
    verification_status: str            # CURRENT | REQUIRED | ...
    evidence_status: str               # CURRENT | INVALIDATED | ...
    invalidation_events: List[Dict] = field(default_factory=list)
    reason: str = ""
    evidence_record_ids: List[str] = field(default_factory=list)


def new_record_id(prefix: str = "ev") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def hash_content(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]
