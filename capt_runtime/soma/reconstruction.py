"""Reconstruction checks for SOMA compressed trajectories."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Optional

from .reducer import ReducerResult
from .trajectory import CRITICAL_IMPORTANCE, CodingTrajectory, event_key


@dataclass(frozen=True)
class ReconstructionReport:
    preserved_events: int
    total_critical_events: int
    preservation_ratio: Optional[float]


def evaluate_reconstruction(
    original: CodingTrajectory,
    compressed: ReducerResult,
) -> ReconstructionReport:
    """Measure whether critical trajectory signals survived compression."""
    if not isinstance(compressed, ReducerResult):
        raise TypeError("compressed value must satisfy ReducerResult")
    critical = Counter(
        event_key(event)
        for event in original.events
        if event.importance >= CRITICAL_IMPORTANCE
    )
    retained = Counter(event_key(event) for event in compressed.events)
    total = sum(critical.values())
    preserved = sum(
        min(count, retained.get(key, 0))
        for key, count in critical.items()
    )
    return ReconstructionReport(
        preserved_events=preserved,
        total_critical_events=total,
        preservation_ratio=(preserved / total) if total else None,
    )
