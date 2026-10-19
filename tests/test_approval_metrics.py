"""Unit tests for approval-gate metrics (upgrade #8 primitive)."""
import pytest

from capt_runtime.approval_metrics import (
    ApprovalMetricsError,
    ApprovalRecord,
    approval_metrics,
)


def _rec(decision, latency, overturned=False, i=0):
    return ApprovalRecord(f"r{i}", decision, latency, overturned)


def test_flags_rubber_stamp_all_approve_fast():
    recs = [_rec("approve", 1.0, i=i) for i in range(25)]
    m = approval_metrics(recs)
    assert m.approve_rate == 1.0 and m.median_latency_s == 1.0
    assert m.fast_decision_rate == 1.0 and m.rubber_stamp is True


def test_small_sample_is_not_flagged():
    recs = [_rec("approve", 1.0, i=i) for i in range(10)]
    assert approval_metrics(recs).rubber_stamp is False


def test_real_denials_are_not_rubber_stamp():
    recs = [_rec("approve", 1.0, i=i) for i in range(13)] + [_rec("deny", 1.0, i=i) for i in range(12)]
    m = approval_metrics(recs)
    assert m.approve_rate == 13 / 25 and m.rubber_stamp is False


def test_overturn_rate_among_approvals():
    recs = [_rec("approve", 1.0, overturned=True, i=0), _rec("approve", 1.0, i=1), _rec("deny", 1.0, i=2)]
    assert approval_metrics(recs).overturn_rate == 0.5


def test_median_latency_even_and_odd():
    odd = [_rec("approve", x, i=i) for i, x in enumerate([1.0, 2.0, 3.0])]
    assert approval_metrics(odd).median_latency_s == 2.0
    even = [_rec("approve", x, i=i) for i, x in enumerate([1.0, 2.0, 3.0, 4.0])]
    assert approval_metrics(even).median_latency_s == 2.5


def test_invalid_decision_and_negative_latency_and_empty_raise():
    with pytest.raises(ApprovalMetricsError):
        approval_metrics([_rec("maybe", 1.0)])
    with pytest.raises(ApprovalMetricsError):
        approval_metrics([_rec("approve", -1.0)])
    with pytest.raises(ApprovalMetricsError):
        approval_metrics([])
