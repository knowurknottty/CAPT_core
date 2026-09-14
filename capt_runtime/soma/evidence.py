"""CAPT evidence adapters for SOMA trajectory construction.

Keeps runtime evidence formats separate from subnet benchmarking.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from .trajectory import CodingTrajectory, extract_events


DEFAULT_IMPORTANCE = {
    "failure": 1.0,
    "error": 0.95,
    "test": 0.9,
    "decision": 0.85,
    "constraint": 0.85,
    "diff": 0.8,
    "commit": 0.75,
}


def normalize_record(record: Dict[str, Any]) -> Dict[str, Any]:
    kind = str(record.get("kind", "unknown"))
    importance = record.get("importance")
    if importance is None:
        importance = DEFAULT_IMPORTANCE.get(kind, 0.1)
    return {
        "kind": kind,
        "content": str(record.get("content", "")),
        "importance": float(importance),
        "source": record.get("source", "capt"),
    }


def from_evidence_records(records: Iterable[Dict[str, Any]]) -> CodingTrajectory:
    normalized: List[Dict[str, Any]] = [normalize_record(record) for record in records]
    return extract_events(normalized)


__all__ = ["from_evidence_records", "normalize_record"]
