"""CAPT-SOMA trajectory extraction primitives.

Keeps coding trajectory evidence separate from compression policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class TrajectoryEvent:
    kind: str
    content: str
    importance: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CodingTrajectory:
    events: List[TrajectoryEvent]

    def ordered_events(self) -> List[TrajectoryEvent]:
        """Return events preserving causal order."""
        return list(self.events)


def extract_events(records: List[Dict[str, Any]]) -> CodingTrajectory:
    """Convert CAPT evidence records into SOMA trajectory events."""
    events = []
    for record in records:
        events.append(
            TrajectoryEvent(
                kind=record.get("kind", "unknown"),
                content=str(record.get("content", "")),
                importance=float(record.get("importance", 0.0)),
                metadata={"source": record.get("source")},
            )
        )
    return CodingTrajectory(events)
