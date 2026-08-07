"""CAPT Runtime mandatory memory trigger subsystem (M1-memory, ADR-DT-M1-MEM-001).

This package is the AUTHORITATIVE home of CAPT memory behavior. It is NOT a
port of capt_solo.memory (which is implemented but disconnected from
capt_runtime). The desktop and drivers are projection/execution surfaces only;
they never own memory logic, authority, or the trigger decision.

Components:
- policy: MemoryTriggerPolicy model + 32k-step validation + precedence.
- accounting: authoritative context accounting (token estimation, budget,
  next trigger boundary, trigger state).
- store: in-ledger memory store (records with provenance/trust/consent).
- query: typed MemoryQuery construction + retrieval against the store.
- contextpack: idempotent ContextPack assembly + digest.
- engine: MemoryTriggerEngine — owns trigger state, enforces mandatory path,
  integrates with DriverHost dispatch and the Hermes driver boundary.
"""

from .policy import (
    TRIGGER_INTERVAL_TOKENS,
    MemoryTriggerPolicy,
    PolicySource,
    validate_policy_steps,
    effective_policy,
    precedence_rank,
)
from .accounting import ContextAccounting, ContextUsage, TriggerState
from .store import MemoryStore, MemoryRecord
from .query import build_memory_query
from .contextpack import build_context_pack
from .engine import MemoryTriggerEngine, MemoryEnforcementError
from .governor import MemoryGovernor

__all__ = [
    "TRIGGER_INTERVAL_TOKENS",
    "MemoryTriggerPolicy",
    "PolicySource",
    "validate_policy_steps",
    "effective_policy",
    "precedence_rank",
    "ContextAccounting",
    "ContextUsage",
    "TriggerState",
    "MemoryStore",
    "MemoryRecord",
    "build_memory_query",
    "ContextPackBuilder",
    "build_context_pack",
    "MemoryTriggerEngine",
    "MemoryEnforcementError",
    "MemoryGovernor",
]
