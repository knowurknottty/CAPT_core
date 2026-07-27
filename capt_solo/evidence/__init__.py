"""CAPT Evidence Engine — governed evidence, invalidation, reuse, and proof graph.

This package implements Phases 1-4, 6-9 of the Long-Horizon Engineering Pass:
- core: EvidenceRecord / EvidenceClaim / EvidenceSource / EvidenceClass /
  EvidenceStatus / EvidenceScope / EvidenceRelation / EvidenceBundle /
  EvidenceQuery / EvidenceDecision
- invalidation: InvalidationEvent / Reason / Rule / Scope / Decision / Graph
- reuse: deterministic evidence-reuse decision engine
- proof_graph: lightweight indexed claim/evidence/verification/invalidation graph
- workspace_isolation: project boundary (.capt/), scope enforcement
- promotion: memory-promotion governance (workspace -> project -> global)
- selfmod: self-modification governance
- checkpoint: mission checkpoint + restart recovery
- metrics: long-session efficiency controls + anti-loop guards

Verification (VSI) answers "what was proven about a specific state?".
Evidence answers "why is that proof justified, where is the support, does it still apply?".
Invalidation answers "what concrete event caused a proof to stop applying?".
"""
from .core import (
    EvidenceRecord, EvidenceClaim, EvidenceSource, EvidenceClass, EvidenceStatus,
    EvidenceScope, EvidenceRelation, EvidenceBundle, EvidenceQuery, EvidenceDecision,
)
from .invalidation import (
    InvalidationEvent, InvalidationReason, InvalidationRule, InvalidationScope,
    InvalidationDecision, InvalidationGraph, scan_invalidation,
)
from .reuse import EvidenceReuseEngine, ReuseOutcome
from .proof_graph import ProofGraph
from .workspace_isolation import (
    ProjectWorkspace, ProjectContext, WorkspaceScope, BindState, WorkspaceIsolationError,
)
from .promotion import (
    PromotionPipeline, MemoryCandidate, PromotionState, PromotionError,
)
from .selfmod import (
    SelfModificationGovernor, SelfModificationRecord, SelfModState, SelfModError,
)
from .checkpoint import (
    MissionCheckpoint, CheckpointStore, CheckpointStatus, detect_divergence, resume_plan,
)
from .metrics import EfficiencyMetrics, AntiLoopGuard

__all__ = [
    "EvidenceRecord", "EvidenceClaim", "EvidenceSource", "EvidenceClass",
    "EvidenceStatus", "EvidenceScope", "EvidenceRelation", "EvidenceBundle",
    "EvidenceQuery", "EvidenceDecision",
    "InvalidationEvent", "InvalidationReason", "InvalidationRule", "InvalidationScope",
    "InvalidationDecision", "InvalidationGraph", "scan_invalidation",
    "EvidenceReuseEngine", "ReuseOutcome", "ProofGraph",
    "ProjectWorkspace", "ProjectContext", "WorkspaceScope", "BindState",
    "WorkspaceIsolationError",
    "PromotionPipeline", "MemoryCandidate", "PromotionState", "PromotionError",
    "SelfModificationGovernor", "SelfModificationRecord", "SelfModState", "SelfModError",
    "MissionCheckpoint", "CheckpointStore", "CheckpointStatus", "detect_divergence",
    "resume_plan", "EfficiencyMetrics", "AntiLoopGuard",
]
