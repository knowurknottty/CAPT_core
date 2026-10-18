"""Unit tests for the calibration scorer (upgrade #3 primitive)."""
import pytest

from capt_runtime.calibration import (
    CalibrationError,
    ResolvedClaim,
    brier_score,
    reliability_bins,
    score_by_key,
)


def _r(key, c, ok):
    return ResolvedClaim(key, c, ok)


def test_brier_perfect_is_zero():
    assert brier_score([_r("m", 1.0, True), _r("m", 0.0, False)]) == 0.0


def test_brier_worst_is_one():
    assert brier_score([_r("m", 1.0, False)]) == 1.0


def test_brier_half_always_is_quarter():
    assert brier_score([_r("m", 0.5, True), _r("m", 0.5, False)]) == 0.25


def test_confidence_out_of_range_raises():
    with pytest.raises(CalibrationError):
        brier_score([_r("m", 1.5, True)])


def test_empty_brier_raises():
    with pytest.raises(CalibrationError):
        brier_score([])


def test_reliability_bin_routing_and_edges():
    bins = reliability_bins([_r("m", 0.05, False), _r("m", 0.95, True), _r("m", 1.0, True)], n_bins=10)
    assert bins[0].count == 1
    assert bins[9].count == 2
    assert bins[9].empirical_accuracy == 1.0


def test_score_by_key_reports_coverage():
    s = score_by_key([_r("fast", 1.0, True), _r("fast", 1.0, False), _r("slow", 0.5, True)])
    assert set(s) == {"fast", "slow"}
    assert s["fast"].n == 2 and s["slow"].n == 1
    assert s["fast"].brier == 0.5
