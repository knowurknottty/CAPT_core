"""Reconstruction checks for SOMA compressed trajectories."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .trajectory import CodingTrajectory


@dataclass(frozen=True)
class ReconstructionReport:
    preserved_events: int
    total_critical_events: int
    preservation_ratio: float


def _event_key(event: Any) -> tuple[str, str]:
    return (str(getattr(event, "kind", "unknown")), str(getattr(event, "content", "")))


def evaluate_reconstruction(
    original: CodingTrajectory,
    compressed: CodingTrajectory,
) -> ReconstructionReport:
    """Measure whether critical trajectory signals survived compression."""
    critical = {
        _event_key(event)
        for event in original.events
        if event.importance >= 0.8
    }
    retained = {_event_key(event) for event in compressed.events}

    total = max(1, len(critical))
    preserved = len(critical.intersection(retained))

    return ReconstructionReport(
        preserved_events=preserved,
        total_critical_events=total,
        preservation_ratio=preserved / total,
    )
