"""Unit tests for the epistemic information-flow lattice (upgrade #1 core)."""
import pytest

from capt_runtime.lattice import Authority, Confidence, LatticeLabel, meet_all

OBS_SHIP = LatticeLabel(Confidence.OBSERVED, Authority.SHIPPED_ARTIFACT)
INF_ANALYST = LatticeLabel(Confidence.INFERRED, Authority.ANALYST_INFERENCE)


def test_meet_takes_weaker_each_axis():
    a = LatticeLabel(Confidence.OBSERVED, Authority.ANALYST_INFERENCE)
    b = LatticeLabel(Confidence.INFERRED, Authority.SHIPPED_ARTIFACT)
    assert a.meet(b) == LatticeLabel(Confidence.INFERRED, Authority.ANALYST_INFERENCE)


def test_meet_is_commutative_and_idempotent():
    assert OBS_SHIP.meet(INF_ANALYST) == INF_ANALYST.meet(OBS_SHIP)
    assert OBS_SHIP.meet(OBS_SHIP) == OBS_SHIP


def test_summary_of_inferred_cannot_be_observed():
    out = meet_all([OBS_SHIP, INF_ANALYST])
    assert out.confidence == Confidence.INFERRED
    assert out.authority == Authority.ANALYST_INFERENCE


def test_dominates_floor():
    floor = LatticeLabel(Confidence.DERIVED, Authority.CONTROLLED_REPLAY)
    assert OBS_SHIP.dominates(floor)
    assert not INF_ANALYST.dominates(floor)
    assert floor.dominates(floor)


def test_meet_all_empty_raises():
    with pytest.raises(ValueError):
        meet_all([])
