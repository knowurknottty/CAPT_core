"""Canonical Autobiographical Memory (Layer 3).

Per Phase 3F, autobiographical memory is an integration over identity, episodic,
semantic, and temporal memory. It is NOT an unbounded diary dump. It must be:
identity-linked, evidence-linked, temporally ordered, uncertainty-aware,
consent-aware, revisable without silently erasing prior interpretations,
distinguish observation from inference, retain conflicting interpretations,
exportable, migratable, locally stored by default.

Implementation: backed by MemoryEngine (namespace ``autobiographical``), reusing
the canonical fields. Each autobiographical entry links to source episodes
(identity/evidence linkage) and carries explicit observation/inference markers.
Revisions are appended as new entries (never overwrite prior interpretation);
conflicting interpretations are retained side by side. No psychological truth is
claimed — inferred meaning is marked as inference, not fact.
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


class EntryKind(str, Enum):
    OBSERVATION = "observation"
    INFERENCE = "inference"
    EVENT = "event"
    PERIOD = "period"          # chapter / phase
    RELATIONSHIP = "relationship"
    THEME = "theme"            # self-attributed meaning (marked inference)


@dataclass
class AutoEntry:
    entry_id: str
    subject_identity: str
    kind: str
    content: str
    timestamp: float
    confidence: float
    uncertainty: Optional[float] = None
    provenance: str = "unknown"
    source_episodes: List[str] = field(default_factory=list)
    source_evidence: List[str] = field(default_factory=list)
    revision_of: Optional[str] = None      # prior entry this revises (never erased)
    superseded_by: Optional[str] = None    # set when a newer revision exists
    conflicts_with: List[str] = field(default_factory=list)
    consent: str = "unset"
    lifecycle_state: str = "active"

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__


@dataclass
class AutoRevision:
    revision_id: str
    entry_id: str
    prior_content: str
    new_content: str
    timestamp: float
    reason: str


class AutobiographicalMemory:
    """Canonical autobiographical memory store (Layer 3)."""

    NAMESPACE = "autobiographical"

    def __init__(self, engine: Optional[MemoryEngine] = None, *,
                 db_path: Optional[Any] = None) -> None:
        self._eng = engine or MemoryEngine(db_path=db_path)

    def add_entry(
        self,
        *,
        subject_identity: str,
        kind: str,
        content: str,
        confidence: float = 1.0,
        uncertainty: Optional[float] = None,
        provenance: str = "unknown",
        source_episodes: Optional[List[str]] = None,
        source_evidence: Optional[List[str]] = None,
        consent: str = "unset",
        timestamp: Optional[float] = None,
    ) -> AutoEntry:
        if not subject_identity:
            raise MemoryError_("subject_identity required")
        if kind not in (k.value for k in EntryKind):
            raise MemoryError_(f"invalid entry kind: {kind}")
        if not (0.0 <= confidence <= 1.0):
            raise MemoryError_("confidence must be 0..1")
        if uncertainty is not None and not (0.0 <= uncertainty <= 1.0):
            raise MemoryError_("uncertainty must be 0..1")
        # inferences/themes must not be silently treated as observations
        if (kind == EntryKind.INFERENCE.value or kind == EntryKind.THEME.value) \
                and provenance == "unknown":
            provenance = "inference"
        entry = AutoEntry(
            entry_id=uuid.uuid4().hex,
            subject_identity=subject_identity,
            kind=kind,
            content=content,
            timestamp=timestamp or time.time(),
            confidence=confidence,
            uncertainty=uncertainty,
            provenance=provenance,
            source_episodes=source_episodes or [],
            source_evidence=source_evidence or [],
            consent=consent,
        )
        self._eng.store(
            json.dumps({"kind": kind, "content": content}),
            memory_id=entry.entry_id,
            namespace=self.NAMESPACE,
            tier="autobiographical",
            provenance=provenance,
            confidence=confidence,
            uncertainty=uncertainty,
            consent=consent,
            identity_link=subject_identity,
            evidence_refs=source_evidence or [],
            metadata={"auto": entry.to_dict()},
            tags=["autobiographical", kind],
        )
        return entry

    def revise(
        self,
        entry_id: str,
        *,
        new_content: str,
        reason: str = "revision",
        confidence: Optional[float] = None,
        uncertainty: Optional[float] = None,
    ) -> AutoEntry:
        """Create a NEW entry revising a prior one. The prior entry is retained
        (never erased); it is linked via revision_of / superseded_by."""
        prior = self.get_entry(entry_id)
        if prior is None:
            raise MemoryError_(f"entry not found: {entry_id}")
        if prior.superseded_by is not None:
            raise MemoryError_("cannot revise an already-superseded entry; revise the latest")
        new = self.add_entry(
            subject_identity=prior.subject_identity,
            kind=prior.kind,
            content=new_content,
            confidence=confidence if confidence is not None else prior.confidence,
            uncertainty=uncertainty if uncertainty is not None else prior.uncertainty,
            provenance=prior.provenance,
            source_episodes=prior.source_episodes,
            source_evidence=prior.source_evidence,
            consent=prior.consent,
            timestamp=time.time(),
        )
        new.revision_of = prior.entry_id
        # persist linkage on both
        self._eng.update(prior.entry_id, metadata={"auto": prior.to_dict()})
        self._eng.update(new.entry_id, metadata={"auto": new.to_dict()})
        # link prior -> superseded
        prior.superseded_by = new.entry_id
        self._eng.update(prior.entry_id, metadata={"auto": prior.to_dict()})
        return new

    def mark_conflict(self, entry_id_a: str, entry_id_b: str) -> None:
        """Retain two conflicting interpretations side by side (no deletion)."""
        a = self.get_entry(entry_id_a)
        b = self.get_entry(entry_id_b)
        if a is None or b is None:
            raise MemoryError_("both entries must exist to mark conflict")
        if entry_id_b not in a.conflicts_with:
            a.conflicts_with.append(entry_id_b)
        if entry_id_a not in b.conflicts_with:
            b.conflicts_with.append(entry_id_a)
        self._eng.update(entry_id_a, metadata={"auto": a.to_dict()})
        self._eng.update(entry_id_b, metadata={"auto": b.to_dict()})

    def get_entry(self, entry_id: str) -> Optional[AutoEntry]:
        mem = self._eng.get(entry_id)
        if mem is None or not mem.metadata.get("auto"):
            return None
        return self._entry_from_mem(mem)

    def list_entries(self, *, subject_identity: Optional[str] = None,
                     kind: Optional[str] = None, limit: int = 100) -> List[AutoEntry]:
        rows = self._eng.list(namespace=self.NAMESPACE, limit=limit)
        out = []
        for m in rows:
            if not m.metadata.get("auto"):
                continue
            e = self._entry_from_mem(m)
            if subject_identity and e.subject_identity != subject_identity:
                continue
            if kind and e.kind != kind:
                continue
            out.append(e)
        return out

    def revision_history(self, entry_id: str) -> List[AutoEntry]:
        """Walk revision_of chain to reconstruct history (prior interpretations
        remain available)."""
        chain: List[AutoEntry] = []
        cur = self.get_entry(entry_id)
        seen = set()
        while cur is not None and cur.entry_id not in seen:
            seen.add(cur.entry_id)
            chain.append(cur)
            if not cur.revision_of:
                break
            cur = self.get_entry(cur.revision_of)
        return list(reversed(chain))

    def delete_entry(self, entry_id: str) -> bool:
        return self._eng.delete(entry_id)

    # ----- helpers -------------------------------------------------------
    @staticmethod
    def _entry_from_mem(mem: Any) -> AutoEntry:
        d = mem.metadata["auto"]
        return AutoEntry(
            entry_id=d["entry_id"],
            subject_identity=d["subject_identity"],
            kind=d["kind"],
            content=d["content"],
            timestamp=d["timestamp"],
            confidence=d["confidence"],
            uncertainty=d.get("uncertainty"),
            provenance=d.get("provenance", "unknown"),
            source_episodes=d.get("source_episodes", []),
            source_evidence=d.get("source_evidence", []),
            revision_of=d.get("revision_of"),
            superseded_by=d.get("superseded_by"),
            conflicts_with=d.get("conflicts_with", []),
            consent=d.get("consent", "unset"),
            lifecycle_state=d.get("lifecycle_state", "active"),
        )
