"""Local SOMA benchmark harness.

Compares context reduction strategies without coupling to CAPT runtime.
The benchmark measures retained utility rather than compression alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List

from .reducer import ReducerResult
from .scoring import utility_density
from .trajectory import CodingTrajectory


@dataclass(frozen=True)
class BenchmarkResult:
    strategy: str
    tokens_retained: int
    utility_retained: float
    density: float


def run_strategy(
    strategy: str,
    trajectory: CodingTrajectory,
    reducer: Callable[[CodingTrajectory], ReducerResult],
) -> BenchmarkResult:
    compressed = reducer(trajectory)
    if not isinstance(compressed, ReducerResult):
        raise TypeError("reducer must return a ReducerResult")

    retained = CodingTrajectory(list(compressed.events))
    tokens = retained.token_count()
    utility = retained.utility_score()
    return BenchmarkResult(
        strategy=strategy,
        tokens_retained=tokens,
        utility_retained=utility,
        density=utility_density(retained_utility=utility, retained_tokens=tokens),
    )


def compare(
    trajectory: CodingTrajectory,
    strategies: List[tuple[str, Callable[[CodingTrajectory], ReducerResult]]],
) -> List[BenchmarkResult]:
    return [run_strategy(name, trajectory, fn) for name, fn in strategies]
