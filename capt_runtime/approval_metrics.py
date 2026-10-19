"""Approval-gate metrics (upgrade #8 primitive).

Operationalizes the observation that a HumanApproval gate approving ~100% of
requests in ~1s carries little information. Pure aggregator over supplied
approval records: approve rate, decide-latency distribution, overturn rate, and
a rubber-stamp flag. Does NOT read the ledger or change gate behavior; a caller
supplies records. Source present + unit-tested; NOT integrated.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


class ApprovalMetricsError(ValueError):
    pass


@dataclass(frozen=True)
class ApprovalRecord:
    request_id: str
    decision: str
    decide_latency_s: float
    later_overturned: bool = False


@dataclass(frozen=True)
class ApprovalMetrics:
    n: int
    approve_rate: float
    median_latency_s: float
    fast_decision_rate: float
    overturn_rate: float
    rubber_stamp: bool


def _median(xs: Sequence[float]) -> float:
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    if n % 2:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2


def approval_metrics(
    records: Sequence[ApprovalRecord],
    *,
    fast_threshold_s: float = 2.0,
    rubber_stamp_approve_rate: float = 0.98,
    rubber_stamp_fast_rate: float = 0.5,
    min_n: int = 20,
) -> ApprovalMetrics:
    if not records:
        raise ApprovalMetricsError("approval_metrics requires at least one record")
    for r in records:
        if r.decision not in ("approve", "deny"):
            raise ApprovalMetricsError(f"invalid decision: {r.decision!r}")
        if r.decide_latency_s < 0:
            raise ApprovalMetricsError(f"negative latency: {r.decide_latency_s!r}")
    n = len(records)
    approvals: list[ApprovalRecord] = [r for r in records if r.decision == "approve"]
    approve_rate = len(approvals) / n
    median_latency = _median([r.decide_latency_s for r in records])
    fast_rate = sum(1 for r in records if r.decide_latency_s <= fast_threshold_s) / n
    overturn_rate = (
        sum(1 for r in approvals if r.later_overturned) / len(approvals) if approvals else 0.0
    )
    rubber_stamp = (
        n >= min_n
        and approve_rate >= rubber_stamp_approve_rate
        and fast_rate >= rubber_stamp_fast_rate
    )
    return ApprovalMetrics(
        n=n,
        approve_rate=approve_rate,
        median_latency_s=median_latency,
        fast_decision_rate=fast_rate,
        overturn_rate=overturn_rate,
        rubber_stamp=rubber_stamp,
    )
