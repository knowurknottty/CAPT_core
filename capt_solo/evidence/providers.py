"""Policy-neutral operational evidence provider contracts.

Providers describe their own observable state.  They do not import or evaluate
CVE policy, so the same snapshots remain usable by other local evidence tools.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Protocol


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class OperationalEvidence:
    evidence_id: str
    kind: str
    timestamp: str
    digest: str
    origin: str
    status: str
    confidence: float
    dependencies: List[str] = field(default_factory=list)
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id, "kind": self.kind,
            "timestamp": self.timestamp, "digest": self.digest,
            "origin": self.origin, "status": self.status,
            "confidence": self.confidence, "dependencies": sorted(self.dependencies),
            "detail": self.detail,
        }


class EvidenceProvider(Protocol):
    """A component-owned, CVE-independent read-only evidence boundary."""
    def status(self) -> str: ...
    def digest(self) -> str: ...
    def timestamp(self) -> str: ...
    def version(self) -> str: ...
    def evidence(self) -> List[OperationalEvidence]: ...


class MissionProvider:
    def __init__(self, store: Any, mission_id: str = "") -> None:
        self._store, self._mission_id = store, mission_id

    def _checkpoints(self) -> List[Any]:
        ids = [self._mission_id] if self._mission_id else sorted(self._store.list_ids())
        return [cp for cp in (self._store.load(i) for i in ids) if cp is not None]

    def status(self) -> str:
        return "current" if self._checkpoints() else "unknown"

    def timestamp(self) -> str:
        values = sorted(cp.timestamp for cp in self._checkpoints())
        return values[-1] if values else "1970-01-01T00:00:00+00:00"

    def version(self) -> str:
        return "mission-checkpoint-v1"

    def evidence(self) -> List[OperationalEvidence]:
        if hasattr(self._store, "events"):
            events = self._store.events(self._mission_id)
            if events:
                return [OperationalEvidence(
                    evidence_id="mission-event:" + item["event_digest"].replace("sha256:", "", 1),
                    kind="mission_" + item["event_type"], timestamp=item["timestamp"],
                    digest=item["event_digest"], origin="mission-runtime", status="current",
                    confidence=1.0, detail=item) for item in events]
        result = []
        for cp in self._checkpoints():
            detail = {"mission_id": cp.mission_id, "status": cp.status,
                      "phase": cp.current_phase, "event": "checkpoint",
                      "commit_references": sorted(cp.commit_references)}
            result.append(OperationalEvidence(
                evidence_id="mission:" + cp.mission_id, kind="mission_checkpoint",
                timestamp=cp.timestamp, digest=_digest(detail), origin="mission-runtime",
                status="verified" if cp.status == "completed" else "current",
                confidence=1.0, detail=detail))
        return sorted(result, key=lambda item: item.evidence_id)

    def digest(self) -> str:
        return _digest([item.to_dict() for item in self.evidence()])


class MemoryProvider:
    """Consumes only MemoryEngine's public continuity_status contract."""
    def __init__(self, memory_engine: Any) -> None:
        self._engine = memory_engine

    def _status(self) -> Dict[str, Any]:
        return self._engine.continuity_status()

    def status(self) -> str:
        return "verified" if self._status().get("integrity") else "invalid"

    def timestamp(self) -> str:
        return self._status().get("timestamp", "1970-01-01T00:00:00+00:00")

    def version(self) -> str:
        return str(self._status().get("schema_version", "unknown"))

    def digest(self) -> str:
        return str(self._status().get("state_digest", ""))

    def evidence(self) -> List[OperationalEvidence]:
        detail = self._status()
        return [OperationalEvidence(
            evidence_id="memory:" + self.digest().replace("sha256:", "", 1),
            kind="memory_runtime", timestamp=self.timestamp(), digest=self.digest(),
            origin="memory-runtime", status=self.status(), confidence=1.0 if detail.get("integrity") else 0.0,
            detail=detail)]


class StaticProvider:
    """Adapter for Learning/Research or other components with explicit facts."""
    def __init__(self, name: str, version: str, timestamp: str,
                 status: str, facts: Iterable[Dict[str, Any]]) -> None:
        self._name, self._version, self._timestamp, self._status = name, version, timestamp, status
        self._facts = sorted((dict(x) for x in facts), key=lambda item: str(item.get("evidence_id", "")))

    def status(self) -> str: return self._status
    def timestamp(self) -> str: return self._timestamp
    def version(self) -> str: return self._version
    def digest(self) -> str: return _digest(self._facts)
    def evidence(self) -> List[OperationalEvidence]:
        return [OperationalEvidence(
            evidence_id=str(f["evidence_id"]), kind=str(f.get("kind", self._name)),
            timestamp=str(f.get("timestamp", self._timestamp)), digest=_digest(f),
            origin=self._name, status=str(f.get("status", self._status)),
            confidence=float(f.get("confidence", 0.0)), dependencies=list(f.get("dependencies", [])),
            detail=dict(f.get("detail", {}))) for f in self._facts]
