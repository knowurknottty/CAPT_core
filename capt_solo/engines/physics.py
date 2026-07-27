"""CAPT Physics Engine — bounded, defensible public physics on the math substrate.

Builds on capt_solo.engines.mathematics (Quantity, Dimension, Number, DerivationTrace).
Does NOT duplicate units/dimensions/expressions/uncertainty/provenance.

Design constraints:
- Every physical relation is explicitly classified:
  ESTABLISHED_LAW, MODEL, APPROXIMATION, EMPIRICAL, HYPOTHESIS, SPECULATIVE.
- Dimensional validation is enforced on all inputs; invalid dims raise DimensionError.
- Models carry explicit assumptions and applicability domains.
- No speculative physics is presented as established fact.
- Deterministic, bounded; solver traces recorded via DerivationTrace.

Scope (honest, bounded): classical mechanics (force/mass/accel, work, energy,
momentum), basic thermodynamics (ideal gas, first law), elementary circuits
(Ohm's law, electrical power), waves (speed/frequency/wavelength). This is NOT
advanced speculative physics; unsupported domains raise PhysicsError.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from capt_solo.engines.mathematics import (
    Dimension, Number, Quantity, DerivationTrace, MathError, DimensionError,
    parse_unit,
)

# Re-export for convenience
__all__ = [
    "PhysicsEngine", "PhysicsError", "RelationClass", "PhysicsResult",
    "PhysicalConstant", "constants", "ClassicalMechanics", "Thermodynamics",
    "Circuits", "Waves",
]


class PhysicsError(MathError):
    """Raised for invalid physical models, dimensions, or unsupported domains."""


class RelationClass(Enum):
    ESTABLISHED_LAW = "established_law"
    MODEL = "model"
    APPROXIMATION = "approximation"
    EMPIRICAL = "empirical"
    HYPOTHESIS = "hypothesis"
    SPECULATIVE = "speculative"


# ---------------------------------------------------------------------------
# Physical constants (SI, approximate values with documented uncertainty)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PhysicalConstant:
    symbol: str
    name: str
    quantity: Quantity
    classification: RelationClass = RelationClass.ESTABLISHED_LAW

    @property
    def value(self) -> float:
        return self.quantity.as_float()


def _c(sym, name, val, unit):
    return PhysicalConstant(sym, name, Quantity(Number.from_float(val), parse_unit(unit)), RelationClass.ESTABLISHED_LAW)


constants: Dict[str, PhysicalConstant] = {
    "c": _c("c", "speed of light in vacuum", 299792458.0, "m/s"),
    "G": _c("G", "gravitational constant", 6.67430e-11, "m^3*kg^-1*s^-2"),
    "h": _c("h", "Planck constant", 6.62607015e-34, "J*s"),
    "k_B": _c("k_B", "Boltzmann constant", 1.380649e-23, "J/K"),
    "g": _c("g", "standard gravity", 9.80665, "m/s^2"),
    "N_A": _c("N_A", "Avogadro constant", 6.02214076e23, "1/mol"),
    "R": _c("R", "gas constant", 8.314462618, "J*mol^-1*K^-1"),
    "epsilon_0": _c("epsilon_0", "vacuum permittivity", 8.8541878128e-12, "F/m"),
    "mu_0": _c("mu_0", "vacuum permeability", 1.25663706212e-6, "N/A^2"),
}


# ---------------------------------------------------------------------------
# Result container with provenance
# ---------------------------------------------------------------------------


@dataclass
class PhysicsResult:
    quantity: Quantity
    relation: str
    classification: RelationClass
    assumptions: List[str] = field(default_factory=list)
    applicability: str = ""
    trace: Optional[DerivationTrace] = None

    def __repr__(self) -> str:
        return (f"PhysicsResult({self.relation}={self.quantity.as_float()!r} "
                f"[{self.classification.value}], dim={self.quantity.dimension})")


# ---------------------------------------------------------------------------
# Classical mechanics
# ---------------------------------------------------------------------------


class ClassicalMechanics:
    """Bounded classical mechanics. All relations ESTABLISHED_LAW / MODEL."""

    @staticmethod
    def force(mass: Quantity, accel: Quantity) -> PhysicsResult:
        if not mass.dimension == parse_unit("kg"):
            raise DimensionError(f"mass must have kg dimension, got {mass.dimension}")
        if not accel.dimension == parse_unit("m/s^2"):
            raise DimensionError(f"accel must have m/s^2 dimension, got {accel.dimension}")
        tr = DerivationTrace()
        tr.record("newton_second_law", "F = m*a", assumptions=["inertial frame", "non-relativistic"],
                  exact=False)
        f = mass * accel
        tr.record("multiply", "F = m*a", prior="F = m*a", result=f"F={f.as_float()}")
        return PhysicsResult(f, "F = m*a", RelationClass.ESTABLISHED_LAW,
                             ["inertial frame", "non-relativistic (v << c)"],
                             "macroscopic, v << c", tr)

    @staticmethod
    def work(force: Quantity, displacement: Quantity) -> PhysicsResult:
        if not force.dimension == parse_unit("N"):
            raise DimensionError(f"force must have N dimension, got {force.dimension}")
        if not displacement.dimension == parse_unit("m"):
            raise DimensionError(f"displacement must have m dimension, got {displacement.dimension}")
        tr = DerivationTrace()
        tr.record("work_definition", "W = F*d (collinear)", assumptions=["force parallel to displacement"],
                  exact=False)
        w = force * displacement
        return PhysicsResult(w, "W = F·d", RelationClass.ESTABLISHED_LAW,
                             ["force collinear with displacement"],
                             "constant force, straight path", tr)

    @staticmethod
    def kinetic_energy(mass: Quantity, velocity: Quantity) -> PhysicsResult:
        if not mass.dimension == parse_unit("kg"):
            raise DimensionError("mass must have kg dimension")
        if not velocity.dimension == parse_unit("m/s"):
            raise DimensionError("velocity must have m/s dimension")
        tr = DerivationTrace()
        tr.record("kinetic_energy", "KE = 1/2 m v^2", assumptions=["non-relativistic"], exact=False)
        v2 = velocity * velocity
        ke = Quantity(Number.from_float(0.5), parse_unit("1")) * mass * v2
        return PhysicsResult(ke, "KE = 1/2 m v^2", RelationClass.ESTABLISHED_LAW,
                             ["non-relativistic (v << c)"], "macroscopic", tr)

    @staticmethod
    def momentum(mass: Quantity, velocity: Quantity) -> PhysicsResult:
        if not mass.dimension == parse_unit("kg"):
            raise DimensionError("mass must have kg dimension")
        if not velocity.dimension == parse_unit("m/s"):
            raise DimensionError("velocity must have m/s dimension")
        tr = DerivationTrace()
        tr.record("momentum", "p = m*v", exact=False)
        p = mass * velocity
        return PhysicsResult(p, "p = m*v", RelationClass.ESTABLISHED_LAW,
                             ["non-relativistic"], "macroscopic", tr)


# ---------------------------------------------------------------------------
# Thermodynamics (bounded)
# ---------------------------------------------------------------------------


class Thermodynamics:
    """Bounded thermodynamics. Ideal gas is a MODEL with explicit assumptions."""

    @staticmethod
    def ideal_gas_pressure(n_moles: Quantity, temp: Quantity, volume: Quantity) -> PhysicsResult:
        if not n_moles.dimension == parse_unit("mol"):
            raise DimensionError("amount must have mol dimension")
        if not temp.dimension == parse_unit("K"):
            raise DimensionError("temperature must have K dimension")
        if not volume.dimension == parse_unit("m^3"):
            raise DimensionError("volume must have m^3 dimension")
        tr = DerivationTrace()
        tr.record("ideal_gas_law", "pV = nRT", assumptions=["point particles", "negligible interactions",
                  "non-relativistic"], exact=False)
        R = constants["R"].quantity
        p = (n_moles * R * temp) / volume
        return PhysicsResult(p, "pV = nRT", RelationClass.MODEL,
                             ["ideal gas: point particles, negligible intermolecular forces",
                              "valid away from condensation/critical point"],
                             "low-to-moderate density, T >> 0K", tr)

    @staticmethod
    def first_law_internal_energy(heat: Quantity, work: Quantity) -> PhysicsResult:
        # ΔU = Q - W  (work done BY system)
        if not heat.dimension == parse_unit("J"):
            raise DimensionError("heat must have J dimension")
        if not work.dimension == parse_unit("J"):
            raise DimensionError("work must have J dimension")
        tr = DerivationTrace()
        tr.record("first_law", "ΔU = Q - W", assumptions=["closed system"], exact=False)
        du = heat - work
        return PhysicsResult(du, "ΔU = Q - W", RelationClass.ESTABLISHED_LAW,
                             ["closed system", "W is work done by system"],
                             "thermodynamic equilibrium states", tr)


# ---------------------------------------------------------------------------
# Elementary circuits
# ---------------------------------------------------------------------------


class Circuits:
    """Bounded DC circuit relations. Ohm's law is a MODEL (linear resistor)."""

    @staticmethod
    def ohms_law(voltage: Optional[Quantity] = None, current: Optional[Quantity] = None,
                resistance: Optional[Quantity] = None) -> PhysicsResult:
        given = [x for x in (voltage, current, resistance) if x is not None]
        if len(given) != 2:
            raise PhysicsError("ohms_law requires exactly two of voltage/current/resistance")
        if voltage is not None and not voltage.dimension == parse_unit("V"):
            raise DimensionError("voltage must have V dimension")
        if current is not None and not current.dimension == parse_unit("A"):
            raise DimensionError("current must have A dimension")
        if resistance is not None and not resistance.dimension == parse_unit("ohm"):
            raise DimensionError("resistance must have ohm dimension")
        tr = DerivationTrace()
        tr.record("ohms_law", "V = I*R", assumptions=["linear (ohmic) resistor", "steady DC"], exact=False)
        if voltage is None:
            r = current * resistance
            return PhysicsResult(r, "V = I*R", RelationClass.MODEL,
                                 ["ohmic (linear) resistor", "steady state"], "DC", tr)
        if current is None:
            i = voltage / resistance
            return PhysicsResult(i, "V = I*R", RelationClass.MODEL,
                                 ["ohmic (linear) resistor", "steady state"], "DC", tr)
        # resistance = V / I
        r = voltage / current
        return PhysicsResult(r, "V = I*R", RelationClass.MODEL,
                             ["ohmic (linear) resistor", "steady state"], "DC", tr)

    @staticmethod
    def electrical_power(voltage: Quantity, current: Quantity) -> PhysicsResult:
        if not voltage.dimension == parse_unit("V"):
            raise DimensionError("voltage must have V dimension")
        if not current.dimension == parse_unit("A"):
            raise DimensionError("current must have A dimension")
        tr = DerivationTrace()
        tr.record("electrical_power", "P = V*I", exact=False)
        p = voltage * current
        return PhysicsResult(p, "P = V*I", RelationClass.ESTABLISHED_LAW,
                             ["steady state"], "DC or instantaneous", tr)


# ---------------------------------------------------------------------------
# Waves
# ---------------------------------------------------------------------------


class Waves:
    """Bounded wave relations. v = f λ is ESTABLISHED_LAW for linear media."""

    @staticmethod
    def wave_speed(frequency: Quantity, wavelength: Quantity) -> PhysicsResult:
        if not frequency.dimension == parse_unit("Hz"):
            raise DimensionError("frequency must have Hz dimension")
        if not wavelength.dimension == parse_unit("m"):
            raise DimensionError("wavelength must have m dimension")
        tr = DerivationTrace()
        tr.record("wave_relation", "v = f*λ", assumptions=["linear, non-dispersive medium"], exact=False)
        v = frequency * wavelength
        return PhysicsResult(v, "v = f*λ", RelationClass.ESTABLISHED_LAW,
                             ["linear non-dispersive medium"], "propagating wave", tr)


# ---------------------------------------------------------------------------
# Public facade
# ---------------------------------------------------------------------------


class PhysicsEngine:
    """Bounded, safe public physics engine (built on mathematics substrate)."""

    def __init__(self) -> None:
        self.mechanics = ClassicalMechanics()
        self.thermo = Thermodynamics()
        self.circuits = Circuits()
        self.waves = Waves()
        self.constants = constants

    def classify(self, relation: str) -> RelationClass:
        """Look up the classification of a known relation (honesty check)."""
        known = {
            "F = m*a": RelationClass.ESTABLISHED_LAW,
            "W = F·d": RelationClass.ESTABLISHED_LAW,
            "KE = 1/2 m v^2": RelationClass.ESTABLISHED_LAW,
            "p = m*v": RelationClass.ESTABLISHED_LAW,
            "pV = nRT": RelationClass.MODEL,
            "ΔU = Q - W": RelationClass.ESTABLISHED_LAW,
            "V = I*R": RelationClass.MODEL,
            "P = V*I": RelationClass.ESTABLISHED_LAW,
            "v = f*λ": RelationClass.ESTABLISHED_LAW,
        }
        if relation not in known:
            raise PhysicsError(f"unknown relation: {relation!r} (cannot assert classification)")
        return known[relation]
