"""CAPT Solo — canonical standalone CAPT Agent Runner (ADR-0001, Outcome C).

This package is the canonical OUTER-LOOP composition and control boundary. It
does NOT introduce a second runtime: it composes the existing single
composition root (:class:`capt_solo.runtime.CAPTRuntime`) and the existing
governed model-execution path (``CAPTRuntime.execute_model_task``), which
already enforces MemoryUseGate-before-provider-invoke at RUNTIME.

Modules:
  contracts  — frozen, versioned data contracts (Intent is first-class here).
  boot       — fail-closed boot pipeline (workspace/mission/checkpoint/
               directives/ContextPack/MemoryUseGate).
  runner     — turn loop composing CAPTRuntime + ModelProvider + CTP + KHSB +
               ClaimGuard + checkpoints. No duplicate runtime.

Out of V1 scope (do not add here): tools, swarm, marketplace, web UI, TUI,
plugin ecosystem, advanced scheduling, autonomous exploration.
"""

from __future__ import annotations

from capt_solo.agent.contracts import (
    AGENT_SCHEMA_VERSION,
    EXECUTION_MODE_BLOCKED,
    EXECUTION_MODE_BOOTSTRAP_DEGRADED,
    EXECUTION_MODE_GOVERNED,
    OUTPUT_MODES,
    AgentBootRequest,
    AgentBootResult,
    AgentMemoryBootTrace,
    AgentRunState,
    AgentTurnRequest,
    AgentTurnResult,
    IntentRecord,
    OutputPolicy,
)

__all__ = [
    "AGENT_SCHEMA_VERSION",
    "EXECUTION_MODE_GOVERNED",
    "EXECUTION_MODE_BOOTSTRAP_DEGRADED",
    "EXECUTION_MODE_BLOCKED",
    "OUTPUT_MODES",
    "IntentRecord",
    "OutputPolicy",
    "AgentBootRequest",
    "AgentBootResult",
    "AgentRunState",
    "AgentTurnRequest",
    "AgentTurnResult",
    "AgentMemoryBootTrace",
    "boot",
    "AgentRunner",
    "resume_report",
]


def __getattr__(name):  # lazy to avoid importing runtime at package import time
    if name in ("boot",):
        from capt_solo.agent.boot import boot as _boot
        return _boot
    if name in ("AgentRunner", "resume_report"):
        from capt_solo.agent import runner as _runner
        return getattr(_runner, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
