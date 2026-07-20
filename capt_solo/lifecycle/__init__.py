"""CAPT Solo v0.3 — Adaptive Memory Lifecycle public surface.

This package is the ONLY sanctioned import path for the adaptive layer
(lifecycle, sessions, procedures, prospective memory, retrieval
feedback, optional semantic adapter). It re-exports stable public
classes and functions and hides implementation details.

Adding a future capability (real semantic adapter, federation) means
adding to this surface — never changing existing names/signatures
in a breaking way within a major version.
"""

from capt_solo.lifecycle.feedback import (
    ADAPTATION_KEYS,
    FEEDBACK_KINDS,
    RetrievalFeedback,
)
from capt_solo.lifecycle.lifecycle import (
    LifecycleEngine,
    LifecycleState,
    MemoryTier,
    PromotionEvaluation,
    RetentionClass,
    VALID_TRANSITIONS,
)
from capt_solo.lifecycle.procedures import Procedure, ProcedureStore
from capt_solo.lifecycle.prospective import (
    ProspectiveIntent,
    ProspectiveStore,
    PROSPECTIVE_KINDS,
    PROSPECTIVE_STATUSES,
)
from capt_solo.lifecycle.semantic import (
    DisabledSemanticAdapter,
    SemanticAdapter,
    get_adapter,
    register_adapter,
)
from capt_solo.lifecycle.sessions import (
    Checkpoint,
    RestartPacket,
    SessionRuntime,
    SESSION_STATUSES,
)
from capt_solo.lifecycle.manager import LifecycleManager

__all__ = [
    # lifecycle
    "LifecycleEngine", "LifecycleState", "MemoryTier",
    "PromotionEvaluation", "RetentionClass", "VALID_TRANSITIONS",
    # sessions
    "SessionRuntime", "Checkpoint", "RestartPacket", "SESSION_STATES",
    # procedures
    "ProcedureStore", "Procedure",
    # prospective
    "ProspectiveStore", "ProspectiveIntent",
    "PROSPECTIVE_KINDS", "PROSPECTIVE_STATES",
    # feedback
    "RetrievalFeedback", "FEEDBACK_KINDS", "ADAPTATION_KEYS",
    # semantic (optional)
    "SemanticAdapter", "DisabledSemanticAdapter", "get_adapter",
    "register_adapter", "LifecycleManager",
]
