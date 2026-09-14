"""CAPT-SOMA benchmark corpus primitives."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .evidence import from_evidence_records
from .trajectory import CRITICAL_IMPORTANCE, CodingTrajectory


@dataclass
class CodingTaskCase:
    name: str
    trajectory: CodingTrajectory
    expected_critical_events: List[str] = field(default_factory=list)


def build_case(name: str, events: List[dict]) -> CodingTaskCase:
    trajectory = from_evidence_records(events)
    return CodingTaskCase(
        name=name,
        trajectory=trajectory,
        expected_critical_events=[
            event.kind
            for event in trajectory.events
            if event.importance >= CRITICAL_IMPORTANCE
        ],
    )
