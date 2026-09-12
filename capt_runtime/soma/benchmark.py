"""Local SOMA benchmark harness.

Compares context reduction strategies without coupling to CAPT runtime.
The benchmark measures retained utility rather than compression alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List

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
    reducer: Callable[[CodingTrajectory], CodingTrajectory],
) -> BenchmarkResult:
    compressed = reducer(trajectory)
    tokens = max(1, compressed.token_count())
    utility = compressed.utility_score()
    return BenchmarkResult(
        strategy=strategy,
        tokens_retained=tokens,
        utility_retained=utility,
        density=utility_density(retained_utility=utility, retained_tokens=tokens),
    )


def compare(
    trajectory: CodingTrajectory,
    strategies: List[tuple[str, Callable[[CodingTrajectory], CodingTrajectory]]],
) -> List[BenchmarkResult]:
    return [run_strategy(name, trajectory, fn) for name, fn in strategies]
