"""CAPT-SOMA benchmark corpus primitives.

Keeps benchmark cases separate from runtime memory.
"""

from dataclasses import dataclass, field
from typing import List

from .trajectory import CodingTrajectory, TrajectoryEvent


@dataclass
class CodingTaskCase:
    name: str
    trajectory: CodingTrajectory
    expected_critical_events: List[str] = field(default_factory=list)


def build_case(name: str, events: List[dict]) -> CodingTaskCase:
    trajectory = CodingTrajectory(
        events=[TrajectoryEvent(**event) for event in events]
    )
    return CodingTaskCase(
        name=name,
        trajectory=trajectory,
        expected_critical_events=[
            event["kind"] for event in events
            if event.get("importance", 0) >= 0.8
        ],
    )
