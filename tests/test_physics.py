"""Tests for the CAPT Physics Engine.

Covers: dimensional validation, established-law vs model classification,
bounded domains, negative tests for invalid dimensions, and honesty of
classification (no speculative physics presented as established).
"""
import pytest

from capt_solo.engines.mathematics import Number, Quantity, parse_unit, DimensionError
from capt_solo.engines.physics import (
    PhysicsEngine, PhysicsError, RelationClass, ClassicalMechanics,
    Thermodynamics, Circuits, Waves, constants,
)


def _q(v, unit):
    return Quantity(Number.from_float(v), parse_unit(unit))


# ---------------------------------------------------------------------------
# Classical mechanics
# ---------------------------------------------------------------------------


def test_newton_second_law():
    eng = PhysicsEngine()
    m = _q(2.0, "kg")
    a = _q(3.0, "m/s^2")
    r = eng.mechanics.force(m, a)
    assert abs(r.quantity.as_float() - 6.0) < 1e-9
    assert r.classification == RelationClass.ESTABLISHED_LAW
    assert r.quantity.dimension == parse_unit("N")


def test_work():
    eng = PhysicsEngine()
    f = _q(10.0, "N")
    d = _q(2.0, "m")
    r = eng.mechanics.work(f, d)
    assert abs(r.quantity.as_float() - 20.0) < 1e-9
    assert r.quantity.dimension == parse_unit("J")


def test_kinetic_energy():
    eng = PhysicsEngine()
    m = _q(2.0, "kg")
    v = _q(3.0, "m/s")
    r = eng.mechanics.kinetic_energy(m, v)
    # 0.5 * 2 * 9 = 9
    assert abs(r.quantity.as_float() - 9.0) < 1e-9
    assert r.quantity.dimension == parse_unit("J")


def test_momentum():
    eng = PhysicsEngine()
    m = _q(4.0, "kg")
    v = _q(5.0, "m/s")
    r = eng.mechanics.momentum(m, v)
    assert abs(r.quantity.as_float() - 20.0) < 1e-9
    assert r.quantity.dimension == parse_unit("kg*m/s")


def test_force_wrong_dimension():
    eng = PhysicsEngine()
    bad_mass = _q(2.0, "s")  # not kg
    a = _q(3.0, "m/s^2")
    with pytest.raises(DimensionError):
        eng.mechanics.force(bad_mass, a)


# ---------------------------------------------------------------------------
# Thermodynamics
# ---------------------------------------------------------------------------


def test_ideal_gas():
    eng = PhysicsEngine()
    n = _q(1.0, "mol")
    T = _q(300.0, "K")
    V = _q(0.025, "m^3")
    r = eng.thermo.ideal_gas_pressure(n, T, V)
    # p = nRT/V = 1*8.314462618*300/0.025 = 99773.55 Pa
    assert abs(r.quantity.as_float() - 99773.551416) < 1e-3
    assert r.classification == RelationClass.MODEL  # honest: it's a model
    assert "ideal gas" in r.assumptions[0]


def test_first_law():
    eng = PhysicsEngine()
    Q = _q(100.0, "J")
    W = _q(40.0, "J")
    r = eng.thermo.first_law_internal_energy(Q, W)
    assert abs(r.quantity.as_float() - 60.0) < 1e-9
    assert r.classification == RelationClass.ESTABLISHED_LAW


# ---------------------------------------------------------------------------
# Circuits
# ---------------------------------------------------------------------------


def test_ohms_law_voltage():
    eng = PhysicsEngine()
    I = _q(2.0, "A")
    R = _q(5.0, "ohm")
    r = eng.circuits.ohms_law(current=I, resistance=R)
    assert abs(r.quantity.as_float() - 10.0) < 1e-9
    assert r.classification == RelationClass.MODEL  # honest: linear resistor


def test_ohms_law_insufficient_args():
    eng = PhysicsEngine()
    with pytest.raises(PhysicsError):
        eng.circuits.ohms_law(voltage=_q(10.0, "V"))


def test_electrical_power():
    eng = PhysicsEngine()
    V = _q(12.0, "V")
    I = _q(2.0, "A")
    r = eng.circuits.electrical_power(V, I)
    assert abs(r.quantity.as_float() - 24.0) < 1e-9
    assert r.classification == RelationClass.ESTABLISHED_LAW


# ---------------------------------------------------------------------------
# Waves
# ---------------------------------------------------------------------------


def test_wave_speed():
    eng = PhysicsEngine()
    f = _q(440.0, "Hz")
    lam = _q(0.78, "m")
    r = eng.waves.wave_speed(f, lam)
    assert abs(r.quantity.as_float() - 343.2) < 1e-6
    assert r.classification == RelationClass.ESTABLISHED_LAW


# ---------------------------------------------------------------------------
# Classification honesty
# ---------------------------------------------------------------------------


def test_classification_lookup():
    eng = PhysicsEngine()
    assert eng.classify("F = m*a") == RelationClass.ESTABLISHED_LAW
    assert eng.classify("pV = nRT") == RelationClass.MODEL
    assert eng.classify("V = I*R") == RelationClass.MODEL
    with pytest.raises(PhysicsError):
        eng.classify("warp_drive_metric")  # unknown -> cannot assert


def test_constants_present():
    assert constants["c"].value == 299792458.0
    assert constants["g"].quantity.dimension == parse_unit("m/s^2")


def test_no_speculative_as_established():
    eng = PhysicsEngine()
    # The engine only exposes classified relations; speculative physics is not
    # present. Assert that no SPECULATIVE relation is returned by any method.
    results = [
        eng.mechanics.force(_q(1.0, "kg"), _q(1.0, "m/s^2")),
        eng.thermo.ideal_gas_pressure(_q(1.0, "mol"), _q(300.0, "K"), _q(0.025, "m^3")),
        eng.circuits.ohms_law(current=_q(1.0, "A"), resistance=_q(1.0, "ohm")),
    ]
    for r in results:
        assert r.classification != RelationClass.SPECULATIVE
