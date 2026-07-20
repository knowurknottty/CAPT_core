"""CAPT Solo public API surface.

This module is the ONLY sanctioned import path for integrators (including the
Hermes plugin and skills). It re-exports stable public classes and functions and
hides all implementation details. Adding a future capability (vector search,
distributed KHSB, federation) means adding to this surface — never changing the
existing names/signatures in a breaking way within a major version.
"""

from __future__ import annotations

from capt_solo.core.config import (
    backup_dir,
    ctp_journal_dir,
    data_dir,
    home_dir,
    khsb_dir,
    memory_db_path,
)
from capt_solo.core.errors import (
    BusError,
    CaptSoloError,
    ConfigurationError,
    IdempotencyError,
    IntegrityError,
    MemoryError_,
    TransactionError,
)
from capt_solo.ctp.journal import CTPRuntime, Receipt
from capt_solo.khsb.bus import KHSB, Message
from capt_solo.lifecycle import (
    LifecycleEngine,
    LifecycleState,
    MemoryTier,
    ProcedureStore,
    Procedure,
    ProspectiveStore,
    ProspectiveIntent,
    RetrievalFeedback,
    SessionRuntime,
    RestartPacket,
    SemanticAdapter,
    DisabledSemanticAdapter,
    get_adapter,
    register_adapter,
    LifecycleManager,
)
from capt_solo.memory.engine import Memory, MemoryEngine
from capt_solo.memory.search import SearchAdapter, SearchHit
from capt_solo.memory import csg, antitoken, context, pipeline, trust, models

__all__ = [
    # config
    "home_dir", "data_dir", "memory_db_path", "ctp_journal_dir", "khsb_dir", "backup_dir",
    # errors
    "CaptSoloError", "MemoryError_", "TransactionError", "BusError",
    "IntegrityError", "ConfigurationError", "IdempotencyError",
    # memory
    "MemoryEngine", "Memory", "SearchAdapter", "SearchHit",
    # memory v0.2
    "csg", "antitoken", "context", "pipeline", "trust", "models",
    # lifecycle v0.3
    "LifecycleEngine", "LifecycleState", "MemoryTier",
    "ProcedureStore", "Procedure", "ProspectiveStore", "ProspectiveIntent",
    "RetrievalFeedback", "SessionRuntime", "RestartPacket",
    "SemanticAdapter", "DisabledSemanticAdapter", "get_adapter",
    "register_adapter", "LifecycleManager",
    # ctp
    "CTPRuntime", "Receipt",
    # khsb
    "KHSB", "Message",
]


def health() -> dict:
    """Lightweight runtime health snapshot (used by capt_health)."""
    from capt_solo.core.config import ensure_dirs
    ensure_dirs()
    mem = MemoryEngine()
    ctp = CTPRuntime()
    bus = KHSB()
    mem_ok = mem.integrity_check()
    ctp_ok = ctp.integrity_check()
    mem.close()
    ctp.close()
    return {
        "status": "ok" if (mem_ok and ctp_ok) else "degraded",
        "memory_integrity": mem_ok,
        "ctp_integrity": ctp_ok,
        "home": str(home_dir()),
    }
