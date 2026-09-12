"""CAPT-SOMA strategy arena."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence

from .reducer import ReducerResult
from .scoring import utility_density
from .trajectory import CRITICAL_IMPORTANCE, CodingTrajectory, event_key


@dataclass(frozen=True)
class ArenaEntry:
    name: str
    reducer: Callable[[CodingTrajectory], ReducerResult]


@dataclass(frozen=True)
class ArenaScore:
    name: str
    retained_events: int
    critical_preservation: Optional[float]
    utility_density: float


def evaluate(
    trajectory: CodingTrajectory,
    entries: Sequence[ArenaEntry],
) -> List[ArenaScore]:
    """Evaluate reducers through the explicit SOMA result contract."""
    critical = Counter(
        event_key(event)
        for event in trajectory.events
        if event.importance >= CRITICAL_IMPORTANCE
    )
    critical_total = sum(critical.values())
    scores: List[ArenaScore] = []

    for entry in entries:
        result = entry.reducer(trajectory)
        if not isinstance(result, ReducerResult):
            raise TypeError("arena reducer must return a ReducerResult")
        retained = CodingTrajectory(list(result.events))
        retained_counts = Counter(event_key(event) for event in retained.events)
        preserved = sum(
            min(count, retained_counts.get(key, 0))
            for key, count in critical.items()
        )
        tokens = retained.token_count()
        utility = retained.utility_score()
        scores.append(
            ArenaScore(
                name=entry.name,
                retained_events=len(retained.events),
                critical_preservation=(preserved / critical_total) if critical_total else None,
                utility_density=utility_density(
                    retained_utility=utility,
                    retained_tokens=tokens,
                ),
            )
        )
    return scores
