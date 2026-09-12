"""CAPT-SOMA strategy arena.

Compares reducers using preservation-first metrics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Sequence

from .trajectory import CodingTrajectory


@dataclass(frozen=True)
class ArenaEntry:
    name: str
    reducer: Callable[[CodingTrajectory], object]


@dataclass(frozen=True)
class ArenaScore:
    name: str
    retained_events: int
    critical_preservation: float
    utility_density: float = 0.0


def _event_key(event: object) -> str:
    if isinstance(event, dict):
        return str(event.get("event_id", event.get("kind", "")))
    return str(getattr(event, "kind", ""))


def evaluate(
    trajectory: CodingTrajectory,
    entries: Sequence[ArenaEntry],
) -> List[ArenaScore]:
    """Evaluate reducers without requiring a specific compression backend."""
    critical = {
        _event_key(event)
        for event in trajectory.events
        if event.importance >= 0.8
    }
    scores: List[ArenaScore] = []

    for entry in entries:
        result = entry.reducer(trajectory)
        retained = getattr(result, "retained", None)
        if retained is None:
            retained = getattr(result, "events", [])

        retained_keys = {_event_key(event) for event in retained}
        denominator = max(1, len(critical))

        scores.append(
            ArenaScore(
                name=entry.name,
                retained_events=len(retained),
                critical_preservation=len(retained_keys & critical) / denominator,
            )
        )

    return scores
