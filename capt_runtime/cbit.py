"""Continuous built-in test (CBIT) probe framework (upgrade #2).

Runs known-bad inputs against a gate and checks the gate rejects them, so a
gate that has silently stopped discriminating is reported ``unverified`` rather
than ``ok``. Pure framework: a Probe carries a category and a payload the gate
is expected to REJECT; run_probes applies a caller-supplied gate predicate and
reports per-probe results plus an aggregate health. Planted payloads carry a
canary marker so a caller can keep them out of real state. Does NOT schedule
itself, plant into the live ledger, or define concrete gates. Source present +
unit-tested; NOT integrated.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

CANARY = "cbit-canary-do-not-commit"


@dataclass(frozen=True)
class Probe:
    name: str
    category: str
    payload: object
    canary: str = CANARY


@dataclass(frozen=True)
class ProbeResult:
    name: str
    category: str
    caught: bool


@dataclass(frozen=True)
class CbitHealth:
    total: int
    caught: int
    status: str
    missed: tuple[str, ...]
    results: tuple[ProbeResult, ...]


# A gate predicate returns True to ADMIT a payload, False to REJECT it.
GatePredicate = Callable[[object], bool]


def run_probes(gate: GatePredicate, probes: Sequence[Probe]) -> CbitHealth:
    if not probes:
        raise ValueError("run_probes requires at least one probe")
    results = tuple(
        ProbeResult(p.name, p.category, caught=not gate(p.payload)) for p in probes
    )
    caught = sum(1 for r in results if r.caught)
    missed = tuple(r.name for r in results if not r.caught)
    status = "ok" if caught == len(results) else "unverified"
    return CbitHealth(len(results), caught, status, missed, results)
