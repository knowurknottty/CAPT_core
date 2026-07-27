"""Canonical ENGRAM — durable memory trace (Layer 3).

Per Phase 3I, an engram is a durable memory trace that undergoes consolidation
(raw -> consolidating -> consolidated). This is a CLEAN implementation in
CAPT_core (external ecosystem source NOT copied; licensing gate [L] avoided).

Backed by MemoryEngine (namespace ``engram``), reusing canonical fields. Links to
source episodes/evidence. Consolidation is explicit and auditable (no silent
state change). No network, no hidden state.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from capt_solo.core.errors import MemoryError_
from capt_solo.memory.engine import MemoryEngine


class ConsolidationState(str, Enum):
    RAW = "raw"
    CONSOLIDATING = "consolidating"
    CONSOLIDATED = "consolidated"
    PRUNED = "pruned"


@dataclass
class Engram:
    engram_id: str
    content: str
    state: str = ConsolidationState.RAW.value
    source_episodes: List[str] = field(default_factory=list)
    source_evidence: List[str] = field(default_factory=list)
    confidence: float = 1.0
    created_at: float = field(default_factory=time.time)
    consolidated_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__


class EngramStore:
    """Canonical engram (durable memory trace) store."""

    NAMESPACE = "engram"

    def __init__(self, engine: Optional[MemoryEngine] = None, *,
                 db_path: Optional[Any] = None) -> None:
        self._eng = engine or MemoryEngine(db_path=db_path)

    def store_trace(
        self, *,
        content: str,
        source_episodes: Optional[List[str]] = None,
        source_evidence: Optional[List[str]] = None,
        confidence: float = 1.0,
        state: str = ConsolidationState.RAW.value,
    ) -> Engram:
        if not content:
            raise MemoryError_("content required")
        if not (0.0 <= confidence <= 1.0):
            raise MemoryError_("confidence must be 0..1")
        if state not in (s.value for s in ConsolidationState):
            raise MemoryError_("invalid consolidation state")
        e = Engram(
            engram_id=uuid.uuid4().hex,
            content=content,
            state=state,
            source_episodes=source_episodes or [],
            source_evidence=source_evidence or [],
            confidence=confidence,
        )
        self._eng.store(
            json.dumps({"content": content, "state": state}),
            memory_id=e.engram_id,
            namespace=self.NAMESPACE,
            tier="engram",
            provenance="engram",
            confidence=confidence,
            evidence_refs=source_evidence or [],
            metadata={"engram": e.to_dict()},
            tags=["engram", state],
        )
        return e

    def set_state(self, engram_id: str, state: str) -> Engram:
        e = self.get_engram(engram_id)
        if e is None:
            raise MemoryError_(f"engram not found: {engram_id}")
        if state not in (s.value for s in ConsolidationState):
            raise MemoryError_("invalid consolidation state")
        e.state = state
        if state == ConsolidationState.CONSOLIDATED.value and e.consolidated_at is None:
            e.consolidated_at = time.time()
        self._eng.update(engram_id, metadata={"engram": e.to_dict()},
                         tags=["engram", state])
        return e

    def consolidate(self, engram_id: str) -> Engram:
        """Move raw -> consolidating -> consolidated (explicit, auditable)."""
        e = self.get_engram(engram_id)
        if e is None:
            raise MemoryError_(f"engram not found: {engram_id}")
        if e.state == ConsolidationState.RAW.value:
            e.state = ConsolidationState.CONSOLIDATING.value
            self._eng.update(engram_id, metadata={"engram": e.to_dict()},
                             tags=["engram", e.state])
        return self.set_state(engram_id, ConsolidationState.CONSOLIDATED.value)

    def get_engram(self, engram_id: str) -> Optional[Engram]:
        mem = self._eng.get(engram_id)
        if mem is None or not mem.metadata.get("engram"):
            return None
        return self._from_mem(mem)

    def list_engrams(self, *, state: Optional[str] = None,
                     limit: int = 100) -> List[Engram]:
        rows = self._eng.list(namespace=self.NAMESPACE, limit=limit)
        out = []
        for m in rows:
            if not m.metadata.get("engram"):
                continue
            e = self._from_mem(m)
            if state and e.state != state:
                continue
            out.append(e)
        return out

    def delete_engram(self, engram_id: str) -> bool:
        return self._eng.delete(engram_id)

    @staticmethod
    def _from_mem(mem: Any) -> Engram:
        d = mem.metadata["engram"]
        return Engram(
            engram_id=d["engram_id"],
            content=d["content"],
            state=d.get("state", ConsolidationState.RAW.value),
            source_episodes=d.get("source_episodes", []),
            source_evidence=d.get("source_evidence", []),
            confidence=d.get("confidence", 1.0),
            created_at=d.get("created_at", mem.created_at),
            consolidated_at=d.get("consolidated_at"),
            metadata=d.get("metadata", {}),
        )
