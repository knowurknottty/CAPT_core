"""Epistemic information-flow lattice labels (upgrade #1 core).

Every value carries a (confidence, authority) label. An operation's output
takes the MEET (greatest lower bound) of its inputs' labels: a result is no
more trustworthy than its weakest input. Promotion to a required floor is a
lattice comparison, so confabulation -- a low-authority input laundered into a
high-authority claim -- becomes a type error rather than a review finding.

This is the pure algebra: ordered levels, a product-lattice meet, and a floor
check. It does NOT attach labels to evidence/claim records or enforce flow at
runtime; that is the schema + authority-core integration step. Status: source
present + unit-tested; NOT integrated.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable


class Confidence(IntEnum):
    INFERRED = 0
    DERIVED = 1
    OBSERVED = 2


class Authority(IntEnum):
    ANALYST_INFERENCE = 0
    EXTERNAL_SERVICE = 1
    HISTORICAL_REFERENCE = 2
    CONTROLLED_REPLAY = 3
    SHIPPED_ARTIFACT = 4


@dataclass(frozen=True)
class LatticeLabel:
    confidence: Confidence
    authority: Authority

    def meet(self, other: LatticeLabel) -> LatticeLabel:
        return LatticeLabel(
            Confidence(min(self.confidence, other.confidence)),
            Authority(min(self.authority, other.authority)),
        )

    def dominates(self, floor: LatticeLabel) -> bool:
        """True iff this label meets ``floor`` on BOTH axes."""
        return self.confidence >= floor.confidence and self.authority >= floor.authority


def meet_all(labels: Iterable[LatticeLabel]) -> LatticeLabel:
    items = list(labels)
    if not items:
        raise ValueError("meet_all requires at least one label")
    acc = items[0]
    for lab in items[1:]:
        acc = acc.meet(lab)
    return acc
