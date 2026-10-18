"""Calibration scoring for confidence-bearing claims.

Upgrade #3 primitive (beyond-parity). Once a confidence-tagged claim resolves,
its predicted confidence can be scored against the outcome. This is the pure
scorer: Brier score and reliability-bin curves, aggregated by an arbitrary key
(lane / vessel / model / provider). It does NOT read claim outcomes from the
ledger or route work; a caller supplies resolved records. Status: source
present + unit-tested; NOT integrated with verification outcomes or routing.

Coverage (n) is reported with every score because resolution is sparse and
biased toward easy-to-check claims: a good Brier over five resolved claims is
not a calibrated agent.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


class CalibrationError(ValueError):
    pass


@dataclass(frozen=True)
class ResolvedClaim:
    key: str
    confidence: float
    correct: bool


@dataclass(frozen=True)
class ReliabilityBin:
    lower: float
    upper: float
    count: int
    mean_confidence: float
    empirical_accuracy: float


@dataclass(frozen=True)
class CalibrationScore:
    key: str
    n: int
    brier: float
    bins: tuple[ReliabilityBin, ...]


def _validate(confidence: float) -> None:
    if not (0.0 <= confidence <= 1.0):
        raise CalibrationError(f"confidence out of range [0,1]: {confidence!r}")


def brier_score(records: Sequence[ResolvedClaim]) -> float:
    if not records:
        raise CalibrationError("brier_score requires at least one record")
    total = 0.0
    for r in records:
        _validate(r.confidence)
        outcome = 1.0 if r.correct else 0.0
        total += (r.confidence - outcome) ** 2
    return total / len(records)


def reliability_bins(records: Sequence[ResolvedClaim], *, n_bins: int = 10) -> list[ReliabilityBin]:
    if n_bins < 1:
        raise CalibrationError("n_bins must be >= 1")
    buckets: list[list[ResolvedClaim]] = [[] for _ in range(n_bins)]
    for r in records:
        _validate(r.confidence)
        idx = min(int(r.confidence * n_bins), n_bins - 1)
        buckets[idx].append(r)
    out: list[ReliabilityBin] = []
    for i, bucket in enumerate(buckets):
        lower, upper = i / n_bins, (i + 1) / n_bins
        if not bucket:
            out.append(ReliabilityBin(lower, upper, 0, 0.0, 0.0))
            continue
        mc = sum(r.confidence for r in bucket) / len(bucket)
        acc = sum(1 for r in bucket if r.correct) / len(bucket)
        out.append(ReliabilityBin(lower, upper, len(bucket), mc, acc))
    return out


def score_by_key(records: Iterable[ResolvedClaim], *, n_bins: int = 10) -> dict[str, CalibrationScore]:
    grouped: dict[str, list[ResolvedClaim]] = {}
    for r in records:
        grouped.setdefault(r.key, []).append(r)
    scores: dict[str, CalibrationScore] = {}
    for key, recs in grouped.items():
        scores[key] = CalibrationScore(
            key=key,
            n=len(recs),
            brier=brier_score(recs),
            bins=tuple(reliability_bins(recs, n_bins=n_bins)),
        )
    return scores
