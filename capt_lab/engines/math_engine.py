"""Bounded, source-traceable mathematical operations from CAPTLang donors."""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable

from capt_lab.contracts import LabEngineRequest, LabEngineResult, LabInputError

_ENGINE_ID = "lab.math"
_ENGINE_VERSION = "0.1.0"
_MAX_CONDUCTOR = 100000
_CYCLOTOMIC_LIMITATIONS = (
    "Donor class-group computation is a placeholder and is not exposed.",
    "Donor unit-group discrete-log implementation is a placeholder and is not exposed.",
    "Result is a deterministic calculation from the adopted donor formulas, not independent mathematical verification.",
)
_MCMILLAN_LIMITATIONS = (
    "Implements the donor McMillan equation only; it is not an Eliashberg solver or material-specific validation.",
    "A numeric transition temperature is a formula evaluation, not a verified superconductivity claim.",
)


def _exact_input(value: Dict[str, Any], fields: Iterable[str]) -> None:
    expected = set(fields)
    actual = set(value)
    missing = expected - actual
    unknown = actual - expected
    if missing:
        raise LabInputError("missing input field(s): %s" % ", ".join(sorted(missing)))
    if unknown:
        raise LabInputError("unknown input field(s): %s" % ", ".join(sorted(unknown)))


def _totient(n: int) -> int:
    result = n
    m = n
    p = 2
    while p * p <= m:
        if m % p == 0:
            while m % p == 0:
                m //= p
            result -= result // p
        p += 1
    if m > 1:
        result -= result // m
    return result


def _prime_divisors(n: int):
    m = n
    p = 2
    while p * p <= m:
        if m % p == 0:
            yield p
            while m % p == 0:
                m //= p
        p += 1
    if m > 1:
        yield m


def _cyclotomic_discriminant(n: int, phi: int) -> int:
    sign = 1 if (phi // 2) % 2 == 0 else -1
    value = pow(n, phi)
    for p in _prime_divisors(n):
        value //= pow(p, phi // (p - 1))
    return value * sign


def _cyclotomic_summary(value: Dict[str, Any]) -> LabEngineResult:
    _exact_input(value, ("conductor",))
    n = value["conductor"]
    if isinstance(n, bool) or not isinstance(n, int) or n < 1 or n > _MAX_CONDUCTOR:
        raise LabInputError("conductor must be an integer in [1, %d]" % _MAX_CONDUCTOR)
    phi = _totient(n)
    rank = 0 if n <= 2 else phi // 2 - 1
    torsion = n if n % 2 == 0 else 2 * n
    return LabEngineResult(
        engine_id=_ENGINE_ID,
        engine_version=_ENGINE_VERSION,
        operation="cyclotomic_summary",
        epistemic_class="calculation",
        observation={
            "conductor": n,
            "degree": phi,
            "discriminant": str(_cyclotomic_discriminant(n, phi)),
            "unitRank": rank,
            "torsionOrder": torsion,
        },
        limitations=_CYCLOTOMIC_LIMITATIONS,
    )


def _finite_number(name: str, raw: Any) -> float:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise LabInputError("%s must be a finite number" % name)
    value = float(raw)
    if not math.isfinite(value):
        raise LabInputError("%s must be a finite number" % name)
    return value


def _mcmillan_tc(value: Dict[str, Any]) -> LabEngineResult:
    _exact_input(value, ("lambda", "omegaLog", "muStar"))
    coupling = _finite_number("lambda", value["lambda"])
    omega_log = _finite_number("omegaLog", value["omegaLog"])
    mu_star = _finite_number("muStar", value["muStar"])
    if coupling < 0.0:
        raise LabInputError("lambda must be >= 0")
    if omega_log <= 0.0:
        raise LabInputError("omegaLog must be > 0")
    if mu_star < 0.0 or mu_star >= 1.0:
        raise LabInputError("muStar must satisfy 0 <= muStar < 1")

    threshold = mu_star * (1.0 + 0.62 * coupling)
    if coupling <= threshold:
        tc = 0.0
    else:
        numerator = 1.04 * (1.0 + coupling)
        denominator = coupling - threshold
        tc = (omega_log / 1.2) * math.exp(-numerator / denominator)
    return LabEngineResult(
        engine_id=_ENGINE_ID,
        engine_version=_ENGINE_VERSION,
        operation="mcmillan_tc",
        epistemic_class="calculation",
        observation={
            "formula": "McMillan",
            "lambda": coupling,
            "omegaLog": omega_log,
            "muStar": mu_star,
            "tcKelvin": tc,
        },
        limitations=_MCMILLAN_LIMITATIONS,
    )


def execute_math(request: LabEngineRequest, context: Dict[str, Any]) -> LabEngineResult:
    if request.engine_id != _ENGINE_ID:
        raise LabInputError("math adapter received wrong engineId")
    if request.operation == "cyclotomic_summary":
        return _cyclotomic_summary(request.input)
    if request.operation == "mcmillan_tc":
        return _mcmillan_tc(request.input)
    raise LabInputError("unsupported math operation %s" % request.operation)
