"""Canonical Episodic Memory (Layer 3).

Per the approved canonical architecture (CANONICAL_ARCHITECTURE L3.3) and
Phase 3D, this is the canonical episodic memory subsystem. It is NOT a replacement
for :class:`capt_solo.lifecycle.sessions.SessionStore` (which is longitudinal
*project* memory); rather it is the event-ordered episodic store that both
SessionStore and Autobiographical Memory build on.

Design:
- Backed by :class:`capt_solo.memory.engine.MemoryEngine`, reusing the canonical
  ``MemoryRecord`` fields (identity_link, evidence_refs, uncertainty, retention,
  consent) added in Phase 3C. No duplicate persistence layer (I-12).
- Episodes are stored in the ``episodic`` namespace with ``tier='episodic'`` and a
  structured ``metadata`` payload (events, context, ordering).
- ECHO-compatible semantics (first-class episodes, explicit event ordering,
  replay eligibility, consolidation eligibility) are implemented cleanly here from
  the approved interface — external ECHO source is NOT copied (licensing gate [L]
  avoided by clean implementation).
- Stable SessionStore compatibility is preserved: SessionStore continues to exist
  and may delegate episode recording to this store.

Canonical API:
    create_episode(*, context, identity_link, evidence_refs, confidence, uncertainty,
                   retention, consent, events) -> Episode
    append_event(episode_id, event) -> Episode
    get_episode(episode_id) -> Optional[Episode]
    list_episodes(*, identity_link, namespace, limit) -> List[Episode]
    retrieval(episode_id) -> RetrievalResult (canonical)
    mark_replay_eligible / mark_consolidation_eligible
    delete_episode(episode_id)
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from capt_solo.core.errors import MemoryError_
from capt_solo.memory.engine import MemoryEngine
from capt_solo.memory.interfaces import (
    ConsentState,
    MemoryRecord,
    RetentionPolicy,
    canonical_to_memory_kwargs,
    memory_to_canonical,
)


EPISODIC_NAMESPACE = "episodic"
EPISODIC_TIER = "episodic"


@dataclass
class EpisodeEvent:
    """A single ordered event within an episode (ontology: observation/inference)."""

    event_id: str
    kind: str            # "observation" | "inference" | "action" | "outcome"
    content: str
    timestamp: float
    confidence: float = 1.0
    uncertainty: Optional[float] = None
    provenance: str = "unknown"
    evidence_refs: List[str] = field(default_factory=list)
    sequence: Optional[int] = None


@dataclass
class Episode:
    """Canonical episodic memory record."""

    episode_id: str
    context: str
    identity_link: Optional[str]
    confidence: float
    uncertainty: Optional[float]
    retention: str
    consent: str
    events: List[EpisodeEvent]
    created_at: float
    updated_at: float
    evidence_refs: List[str] = field(default_factory=list)
    replay_eligible: bool = False
    consolidation_eligible: bool = False
    lifecycle_state: str = "active"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "context": self.context,
            "identity_link": self.identity_link,
            "confidence": self.confidence,
            "uncertainty": self.uncertainty,
            "retention": self.retention,
            "consent": self.consent,
            "evidence_refs": self.evidence_refs,
            "events": [e.__dict__ for e in self.events],
            "replay_eligible": self.replay_eligible,
            "consolidation_eligible": self.consolidation_eligible,
            "lifecycle_state": self.lifecycle_state,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class EpisodicMemory:
    """Canonical episodic memory store (Layer 3)."""

    def __init__(self, engine: Optional[MemoryEngine] = None, *,
                 db_path: Optional[Any] = None) -> None:
        self._eng = engine or MemoryEngine(db_path=db_path)

    # ----- episode lifecycle --------------------------------------------
    def create_episode(
        self,
        *,
        context: str,
        identity_link: Optional[str] = None,
        evidence_refs: Optional[List[str]] = None,
        confidence: float = 1.0,
        uncertainty: Optional[float] = None,
        retention: str = "durable",
        consent: str = "unset",
        events: Optional[List[EpisodeEvent]] = None,
        namespace: str = EPISODIC_NAMESPACE,
    ) -> Episode:
        if not context:
            raise MemoryError_("episode context must be non-empty")
        if not (0.0 <= confidence <= 1.0):
            raise MemoryError_("confidence must be between 0.0 and 1.0")
        if uncertainty is not None and not (0.0 <= uncertainty <= 1.0):
            raise MemoryError_("uncertainty must be between 0.0 and 1.0")
        evs = events or []
        # assign sequence numbers if missing
        for i, ev in enumerate(evs):
            if ev.sequence is None:
                ev.sequence = i
        payload = {
            "episode": True,
            "context": context,
            "events": [e.__dict__ for e in evs],
            "replay_eligible": False,
            "consolidation_eligible": False,
        }
        content = json.dumps({"context": context, "event_count": len(evs)})
        mem = self._eng.store(
            content,
            namespace=namespace,
            tier=EPISODIC_TIER,
            provenance="episodic",
            confidence=confidence,
            uncertainty=uncertainty,
            retention=retention,
            consent=consent,
            identity_link=identity_link,
            evidence_refs=evidence_refs or [],
            metadata=payload,
            tags=["episode"],
        )
        return self._to_episode(mem)

    def append_event(self, episode_id: str, event: EpisodeEvent) -> Episode:
        ep = self.get_episode(episode_id)
        if ep is None:
            raise MemoryError_(f"episode not found: {episode_id}")
        if event.sequence is None:
            event.sequence = len(ep.events)
        ep.events.append(event)
        payload = {
            "episode": True,
            "context": ep.context,
            "events": [e.__dict__ for e in ep.events],
            "replay_eligible": ep.replay_eligible,
            "consolidation_eligible": ep.consolidation_eligible,
        }
        self._eng.update(
            episode_id,
            metadata=payload,
            uncertainty=ep.uncertainty,
            retention=ep.retention,
            consent=ep.consent,
            identity_link=ep.identity_link,
            evidence_refs=ep.evidence_refs,
        )
        return self.get_episode(episode_id)

    def get_episode(self, episode_id: str) -> Optional[Episode]:
        mem = self._eng.get(episode_id)
        if mem is None:
            return None
        return self._to_episode(mem)

    def list_episodes(
        self, *, identity_link: Optional[str] = None,
        namespace: str = EPISODIC_NAMESPACE, limit: int = 100,
    ) -> List[Episode]:
        rows = self._eng.list(namespace=namespace, limit=limit)
        out = []
        for m in rows:
            if m.metadata.get("episode"):
                ep = self._to_episode(m)
                if identity_link is None or ep.identity_link == identity_link:
                    out.append(ep)
        return out

    def mark_replay_eligible(self, episode_id: str, eligible: bool = True) -> Episode:
        ep = self.get_episode(episode_id)
        if ep is None:
            raise MemoryError_(f"episode not found: {episode_id}")
        ep.replay_eligible = eligible
        self._eng.update(episode_id, metadata=self._episode_payload(ep))
        return self.get_episode(episode_id)

    def mark_consolidation_eligible(self, episode_id: str, eligible: bool = True) -> Episode:
        ep = self.get_episode(episode_id)
        if ep is None:
            raise MemoryError_(f"episode not found: {episode_id}")
        ep.consolidation_eligible = eligible
        self._eng.update(episode_id, metadata=self._episode_payload(ep))
        return self.get_episode(episode_id)

    def delete_episode(self, episode_id: str) -> bool:
        return self._eng.delete(episode_id)

    def to_canonical(self, episode_id: str) -> Optional[MemoryRecord]:
        """Return the canonical MemoryRecord for an episode (I-12 single mapping)."""
        mem = self._eng.get(episode_id)
        return memory_to_canonical(mem) if mem else None

    # ----- helpers -------------------------------------------------------
    @staticmethod
    def _episode_payload(ep: Episode) -> Dict[str, Any]:
        return {
            "episode": True,
            "context": ep.context,
            "events": [e.__dict__ for e in ep.events],
            "replay_eligible": ep.replay_eligible,
            "consolidation_eligible": ep.consolidation_eligible,
        }

    @staticmethod
    def _to_episode(mem: Any) -> Episode:
        meta = mem.metadata or {}
        raw_events = meta.get("events", [])
        events = []
        for i, e in enumerate(raw_events):
            if isinstance(e, dict):
                events.append(EpisodeEvent(
                    event_id=e.get("event_id", f"ev-{i}"),
                    kind=e.get("kind", "observation"),
                    content=e.get("content", ""),
                    timestamp=e.get("timestamp", mem.created_at),
                    confidence=e.get("confidence", 1.0),
                    uncertainty=e.get("uncertainty"),
                    provenance=e.get("provenance", "unknown"),
                    evidence_refs=e.get("evidence_refs", []),
                    sequence=e.get("sequence", i),
                ))
        return Episode(
            episode_id=mem.memory_id,
            context=meta.get("context", ""),
            identity_link=mem.identity_link,
            confidence=mem.confidence,
            uncertainty=mem.uncertainty,
            retention=mem.retention,
            consent=mem.consent,
            events=events,
            created_at=mem.created_at,
            updated_at=mem.updated_at,
            evidence_refs=list(mem.evidence_refs),
            replay_eligible=meta.get("replay_eligible", False),
            consolidation_eligible=meta.get("consolidation_eligible", False),
            lifecycle_state=mem.lifecycle_state,
        )
