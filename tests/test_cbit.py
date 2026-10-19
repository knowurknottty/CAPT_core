"""Unit tests for the CBIT probe framework (upgrade #2)."""
import pytest
from capt_runtime.cbit import CANARY, Probe, run_probes


def _bad(name):
    return Probe(name, "injection", {"evil": True})


def test_healthy_gate_catches_all():
    h = run_probes(lambda payload: False, [_bad("p1"), _bad("p2")])
    assert h.status == "ok" and h.caught == 2 and h.missed == ()


def test_broken_gate_is_unverified():
    h = run_probes(lambda payload: True, [_bad("p1"), _bad("p2")])
    assert h.status == "unverified" and h.caught == 0 and set(h.missed) == {"p1", "p2"}


def test_partial_catch_is_unverified():
    good = Probe("good", "injection", {"evil": True})
    leak = Probe("leak", "injection", {"evil": True, "slip": True})

    def gate(payload):
        return bool(payload.get("slip"))

    h = run_probes(gate, [good, leak])
    assert h.status == "unverified" and h.caught == 1 and h.missed == ("leak",)


def test_empty_raises():
    with pytest.raises(ValueError):
        run_probes(lambda payload: False, [])


def test_canary_marker_present_by_default():
    assert Probe("x", "c", {}).canary == CANARY
