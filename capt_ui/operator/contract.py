"""Shared operator contract: typed enums and state views.

This is the single abstraction every UI surface consumes. Presentation layers
render these; they never re-derive or duplicate runtime logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class RuntimeHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


class Verbosity(str, Enum):
    """CaveCAPT operator-controlled verbosity (UI-2). Presentation only."""

    MINIMAL = "minimal"
    NORMAL = "normal"
    DETAILED = "detailed"
    DIAGNOSTIC = "diagnostic"

    @property
    def label(self) -> str:
        return self.value.capitalize()

    @classmethod
    def all(cls) -> List["Verbosity"]:
        return [cls.MINIMAL, cls.NORMAL, cls.DETAILED, cls.DIAGNOSTIC]


class ProviderKind(str, Enum):
    LOCAL = "local"
    CLOUD = "cloud"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"


class ProviderHealth(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    UNKNOWN = "unknown"


class ModelScope(str, Enum):
    """Where a model selection applies (UI-1 / Phase 3)."""

    DEFAULT = "default"
    MISSION = "mission"
    TEMPORARY = "temporary"
    WORKFLOW = "workflow"


@dataclass
class OperatorStatus:
    """Top-line runtime status shown in every surface."""

    health: RuntimeHealth = RuntimeHealth.UNKNOWN
    runtime_version: str = ""
    integrity: str = ""
    head_sequence: int = 0
    active_provider: str = ""
    active_model: str = ""
    context_used: int = 0
    context_limit: int = 0
    memory_active: bool = False
    approvals_pending: int = 0
    checkpoint_available: bool = False
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ApproxRequest:
    request_id: str
    mission_id: str
    task_id: str
    capability: str
    operation: str
    scope: str
    risk: str
    state: str
    policy_reason: str = ""


@dataclass
class EvidenceView:
    claim: str = ""
    verdict: str = ""
    reason: str = ""
    verification: Dict[str, Any] = field(default_factory=dict)
    verifications_by_claim: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    epistemic_ladder: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Dashboard:
    """One projection of the whole operator state (no hidden state)."""

    status: OperatorStatus = field(default_factory=OperatorStatus)
    missions: List[Dict[str, Any]] = field(default_factory=list)
    tasks: List[Dict[str, Any]] = field(default_factory=list)
    approvals: List[ApproxRequest] = field(default_factory=list)
    driver_runs: List[Dict[str, Any]] = field(default_factory=list)
    claims: List[Dict[str, Any]] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    evidence: EvidenceView = field(default_factory=EvidenceView)
    verification: Dict[str, Any] = field(default_factory=dict)
    verifications_by_claim: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    epistemic_ladder: List[Dict[str, Any]] = field(default_factory=list)
    ledger_chain_digest: str = ""
    provider_status: Dict[str, Any] = field(default_factory=dict)
    memory: Dict[str, Any] = field(default_factory=dict)


def health_of(identity: Dict[str, Any], connected: bool) -> RuntimeHealth:
    """Derive operator health from the authoritative identity."""
    if not connected:
        return RuntimeHealth.STOPPED
    if identity.get("integrity") == "ok":
        return RuntimeHealth.HEALTHY
    return RuntimeHealth.DEGRADED


def verdict_ok(evidence: EvidenceView) -> bool:
    """True when the ClaimGuard/verification accepted the claim."""
    return evidence.verdict in ("accept", "approved", "verified")