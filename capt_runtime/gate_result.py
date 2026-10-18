"""Universal gate result (upgrade #1, GateResult).

A four-valued outcome every CAPT gate (containment, review, evidence closure,
replay, CBIT) can return. Only Within proceeds; Exceeds carries a
counterexample; Unsupported/Inconclusive carry a reason. Modeled on the
OpenShell prover's CheckResult, re-authored for CAPT. Combining several gate
results takes the most-blocking outcome, so one non-Within blocks. Pure types +
a combiner; does NOT define concrete gates or wire into the runtime. Source
present + unit-tested; NOT integrated.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum


class GateReason(str, Enum):
    UNSUPPORTED_SHAPE = "unsupported_shape"
    UNRESOLVED_REFERENCE = "unresolved_reference"
    SOLVER_TIMEOUT = "solver_timeout"
    SOLVER_UNKNOWN = "solver_unknown"
    RESOURCE_LIMIT = "resource_limit"
    INVALID_WITNESS = "invalid_witness"
    CANCELLED = "cancelled"
    VERSION_MISMATCH = "version_mismatch"


class GateResult:
    """Base type; a gate returns one of the four subclasses below."""


@dataclass(frozen=True)
class Within(GateResult):
    pass


@dataclass(frozen=True)
class Exceeds(GateResult):
    counterexample: object


@dataclass(frozen=True)
class Unsupported(GateResult):
    reason_code: GateReason
    reason: str


@dataclass(frozen=True)
class Inconclusive(GateResult):
    reason_code: GateReason
    reason: str


def proceeds(result: GateResult) -> bool:
    """Only a Within result admits the action."""
    return isinstance(result, Within)


# Higher = more blocking. A proven violation (Exceeds) outranks 'could not
# prove safe' (Inconclusive/Unsupported), which outranks Within.
_SEVERITY = {Within: 0, Unsupported: 1, Inconclusive: 2, Exceeds: 3}


def combine(results: Sequence[GateResult]) -> GateResult:
    """Return the most-blocking result. Empty is an error (no gate ran)."""
    items = list(results)
    if not items:
        raise ValueError("combine requires at least one gate result")
    return max(items, key=lambda r: _SEVERITY[type(r)])
