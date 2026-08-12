"""Discovery subsystem shared models (v0.7).

Pure dataclasses / enums. No I/O, no authority. These capture the difference
between an OBSERVATION (what was seen, possibly rejected) and a CONCLUSION (an
evidence-backed judgement made elsewhere by CAPT verification/ClaimGuard).

Vocabulary note: source classification is intentionally conservative. A
``compiled_artifact_only`` directory is never labeled "source repository found"
without extra evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


# strategy / result vocabulary (bounded, never silently falls through)
class StrategyResult(str):
    pass


UNAVAILABLE = "unavailable"
NOT_APPLICABLE = "not_applicable"
PERMISSION_DENIED = "permission_denied"
NOT_FOUND = "not_found"
AMBIGUOUS = "ambiguous"
EXHAUSTED = "exhausted"
SOURCE_PRESENT = "source_present"
COMPILED_ARTIFACT_ONLY = "compiled_artifact_only"
SOURCE_NOT_PROVEN = "source_not_proven"
REJECTED = "rejected"
POSSIBLE_REPOSITORY = "possible_repository"
CONTAINER_METADATA_PRESENT = "container_metadata_present"
UNKNOWN = "unknown"


@dataclass
class ScanLimits:
    """Conservative, configurable bounds. No unbounded recursive walks."""
    max_depth: int = 12
    max_files: int = 2000
    max_directories: int = 500
    max_bytes_per_file: int = 8 * 1024 * 1024   # 8 MiB
    max_total_bytes: int = 64 * 1024 * 1024     # 64 MiB
    max_candidates: int = 2000
    timeout_seconds: float = 30.0


@dataclass
class Candidate:
    """A discovery observation. Observation != conclusion."""
    candidate_id: str
    path: str                       # normalized symbolic path
    resolved_path: str              # realpath (after symlink resolution)
    kind: str                       # "file" | "directory" | "bundle" | ...
    strategy: str                   # which ladder rung produced it
    classification: str             # conservative SourceClassification-ish
    confidence: str                 # high | medium | low | unknown
    evidence: List[str] = field(default_factory=list)   # concrete signatures (redacted)
    provenance: Dict[str, Any] = field(default_factory=dict)
    redactions: List[str] = field(default_factory=list)
    accepted: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RejectionRecord:
    """Why a path/candidate was rejected (deterministic, serializable)."""
    path: str
    reason: str                     # outside_allowed_root | symlink_escape | ...
    strategy: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GovernorDecision:
    """Next-action decision from the governor."""
    action: str                     # a ladder rung, owner_clarification, or stop
    reason: str = ""
    ok: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DiscoveryResult:
    """Deterministic output of a discovery run."""
    request_id: str = ""
    strategy_trace: List[Dict[str, Any]] = field(default_factory=list)
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    rejections: List[Dict[str, Any]] = field(default_factory=list)
    negative_evidence: List[Dict[str, Any]] = field(default_factory=list)
    termination: str = ""           # NOT_FOUND | EXHAUSTED | SOURCE_PRESENT | ...
    stop_reason: str = ""
    recommended_next: str = ""
    source_location_confidence: str = "unknown"
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["candidates"] = list(self.candidates)
        d["rejections"] = list(self.rejections)
        return d
