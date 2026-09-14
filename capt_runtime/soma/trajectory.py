"""CAPT-SOMA trajectory extraction primitives.

Keeps coding trajectory evidence separate from compression policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Dict, List

CRITICAL_IMPORTANCE = 0.8


@dataclass(frozen=True)
class TrajectoryEvent:
    kind: str
    content: str
    importance: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        value = float(self.importance)
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError("importance must be finite and within [0, 1]")


def event_key(event: TrajectoryEvent) -> tuple[str, str]:
    """Return the canonical content identity used by SOMA evaluators."""
    return (event.kind, event.content)


@dataclass(frozen=True)
class CodingTrajectory:
    events: List[TrajectoryEvent]

    def ordered_events(self) -> List[TrajectoryEvent]:
        """Return events preserving causal order."""
        return list(self.events)

    def token_count(self) -> int:
        """Return a deterministic content-token estimate for benchmarking."""
        return sum(max(1, (len(event.content) + 3) // 4) for event in self.events)

    def utility_score(self) -> float:
        """Return total declared event importance."""
        return sum(event.importance for event in self.events)


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
