"""Unit tests for the universal gate result (upgrade #1, GateResult)."""
import pytest
from capt_runtime.gate_result import (
    Exceeds,
    GateReason,
    Inconclusive,
    Unsupported,
    Within,
    combine,
    proceeds,
)


def test_only_within_proceeds():
    assert proceeds(Within())
    assert not proceeds(Exceeds(counterexample={"bad": 1}))
    assert not proceeds(Unsupported(GateReason.SOLVER_TIMEOUT, "timed out"))
    assert not proceeds(Inconclusive(GateReason.SOLVER_UNKNOWN, "unknown"))


def test_combine_all_within_is_within():
    r = combine([Within(), Within()])
    assert isinstance(r, Within) and proceeds(r)


def test_combine_blocks_on_any_non_within():
    r = combine([Within(), Inconclusive(GateReason.RESOURCE_LIMIT, "x"), Within()])
    assert isinstance(r, Inconclusive) and not proceeds(r)


def test_exceeds_is_most_blocking():
    r = combine([
        Exceeds(counterexample=1),
        Inconclusive(GateReason.CANCELLED, "c"),
        Unsupported(GateReason.UNSUPPORTED_SHAPE, "u"),
    ])
    assert isinstance(r, Exceeds)


def test_combine_empty_raises():
    with pytest.raises(ValueError):
        combine([])
