"""Canonical external API facade for CAPT_core (Layer 3 / External).

Per Phase 3L, the external interface is hardened: a single, stable, documented
entry point exposes the canonical subsystems. Consumers import from here rather
than reaching into internal modules. The facade fails loudly (raises) on invalid
use instead of silently degrading, except where an explicit optional-capability
contract (I-09) applies.

NOTE: this is a NEW module (capt_solo.capt_facade). The sanctioned public API
surface remains capt_solo.api (integrator/plugin path) — this facade is the
Phase 3L canonical-subsystem surface and does not redefine or replace it (I-11).

No hidden network behavior, no hidden state, no implicit trust. Every constructor
accepts an explicit ``db_path`` or ``engine``; nothing reaches out on import.
"""
from __future__ import annotations

from typing import Any, Optional

from capt_solo.knowledge.evidence import EvidenceStore, VerificationStatus
from capt_solo.knowledge.knowledge import KnowledgeStore, KnowledgeStatus
from capt_solo.memory.autobiographical import AutobiographicalMemory, EntryKind
from capt_solo.memory.engine import MemoryEngine
from capt_solo.memory.episodic import EpisodicMemory
from capt_solo.memory.engram import EngramStore
from capt_solo.memory.hmc import HolographicMemoryCompressor
from capt_solo.execution.boundaries import ExecutionBoundary
from capt_solo.learning.continuous import ContinuousLearner
from capt_solo.learning.dream import DreamConsolidator
from capt_solo.research.adapter import (
    DEFAULT_REGISTRY,
    ResearchAdapterRegistry,
)


class CAPT:
    """Hardened facade over the canonical CAPT_core subsystems.

    All stores share one MemoryEngine when constructed without explicit engines,
    so data is co-located and consistent. Passing ``db_path`` routes everything to
    a single SQLite file (local-first, I-01).
    """

    def __init__(self, *, db_path: Optional[Any] = None,
                 engine: Optional[MemoryEngine] = None) -> None:
        if engine is None and db_path is None:
            # explicit local-first default: in-memory engine (no silent file IO)
            engine = MemoryEngine()
        self._engine = engine or MemoryEngine(db_path=db_path)
        # shared engine across subsystems (no hidden separate DBs)
        self.memory = self._engine
        self.episodic = EpisodicMemory(engine=self._engine)
        self.autobiographical = AutobiographicalMemory(engine=self._engine)
        self.evidence = EvidenceStore(engine=self._engine)
        self.knowledge = KnowledgeStore(engine=self._engine,
                                         evidence_store=self.evidence)
        self.engram = EngramStore(engine=self._engine)
        self.hmc = HolographicMemoryCompressor()
        self.execution = ExecutionBoundary()
        self.continuous = ContinuousLearner(
            knowledge_store=self.knowledge, evidence_store=self.evidence,
            engine=self._engine)
        self.dream = DreamConsolidator(
            engram_store=self.engram, evidence_store=self.evidence,
            knowledge_store=self.knowledge, db_path=None)
        self.research: ResearchAdapterRegistry = DEFAULT_REGISTRY

    def close(self) -> None:
        self._engine.close()

    # convenience passthroughs (explicit, documented)
    def add_evidence(self, *, claim: str, source_refs: list, **kw: Any):
        return self.evidence.add_evidence(claim=claim, source_refs=source_refs, **kw)

    def add_knowledge(self, *, statement: str, evidence_refs: list, **kw: Any):
        return self.knowledge.add_knowledge(
            statement=statement, evidence_refs=evidence_refs, **kw)

    def create_episode(self, *, context: str, **kw: Any):
        return self.episodic.create_episode(context=context, **kw)

    def add_autobiographical(self, *, subject_identity: str, kind: str,
                             content: str, **kw: Any):
        return self.autobiographical.add_entry(
            subject_identity=subject_identity, kind=kind, content=content, **kw)

    def run_execution(self, *, subject: str, scope: str, capabilities, func,
                      consent_scope: Optional[str] = None):
        return self.execution.run(subject=subject, scope=scope,
                                  capabilities=capabilities, func=func,
                                  consent_scope=consent_scope)

    def verify_runtime(self) -> bool:
        """Lightweight self-check: engine reachable + stores instantiable."""
        try:
            self._engine.list(limit=1)
            return True
        except Exception:
            return False


__all__ = ["CAPT", "MemoryEngine"]
