"""Deterministic Discovery Governor (v0.7).

A strategy state machine that decides which bounded observation to try next and
WHEN to stop guessing. It records the escalation ladder position, enforces the
three-failed-guesses -> enumeration invariant, and terminates with an explicit
result instead of looping.

The governor holds no authority: it RECOMMENDS the next strategy. Whether any
follow-on capability is granted stays at RuntimeService / the lease boundary.

Semantics of observe():
  * if a source is located -> decision(action="source_present", ok=True)
  * if a DIRECT GUESS failed and the guess budget is not yet exhausted:
        stay in the guess phase (action = current guess strategy), counting
        the failure; the caller keeps guessing (bounded inputs).
  * on the guess that exhausts the budget -> decision(action=
        "FILESYSTEM_ENUMERATION", reason cites the three-guess rule). The
        governor has now forced a mechanism change; `_forced` latches.
  * once forced (or for non-guess strategies), subsequent observations simply
        advance up the ladder; the position is MONOTONIC (never decreases),
        so repeated failed guesses after a force can never re-enter the guess
        phase or loop. It terminates at STOP.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .models import (
    GovernorDecision,
    NOT_FOUND,
    PERMISSION_DENIED,
    REJECTED,
    SOURCE_PRESENT,
)
from .policy import ESCALATION_LADDER, is_guess

# classifications that count as a failed direct guess
_FAILED_GUESS_CLASS = {
    NOT_FOUND, PERMISSION_DENIED, REJECTED,
    "outside_allowed_root", "symlink_escape", "compiled_artifact_only",
    "source_not_proven", "unavailable", "ambiguous", "exhausted",
}


class DiscoveryGovernor:
    """Escalation state machine with a bounded, monotonic ladder."""

    def __init__(self, *, guess_budget: int = 3,
                 ladder: Optional[Sequence[str]] = None) -> None:
        self._budget = max(1, int(guess_budget))
        self._ladder = list(ladder or ESCALATION_LADDER)
        self._position = 0
        self._direct_guess_failures = 0
        self._forced = False
        self._last_action: Optional[str] = None
        self._history: List[Dict[str, Any]] = []

    # -- public API ---------------------------------------------------------
    def current_strategy(self) -> str:
        return self._ladder[min(self._position, len(self._ladder) - 1)]

    def observe(self, *, strategy: str,
                classification: str) -> GovernorDecision:
        self._history.append({"strategy": strategy,
                              "classification": classification})

        # Positive terminal: source located.
        if classification == SOURCE_PRESENT:
            self._last_action = "source_present"
            return self._decision("source_present", "source located", ok=True)

        # Only direct-guess strategies count toward the guess budget.
        if is_guess(strategy) and not self._forced \
           and classification in _FAILED_GUESS_CLASS:
            self._direct_guess_failures += 1
            if self._direct_guess_failures >= self._budget:
                # HARD INVARIANT: budget exhausted -> force enumeration.
                self._direct_guess_failures = 0
                self._force_enumeration()
                return self._decision(
                    "FILESYSTEM_ENUMERATION",
                    "three failed direct guesses -> force enumeration",
                    ok=True)
            # guess failed but budget not exhausted -> stay in guess phase
            self._last_action = strategy
            return self._decision(
                strategy,
                "guess failed, remaining budget %d" % (
                    self._budget - self._direct_guess_failures),
                ok=True)

        # Non-guess (or already forced): advance monotonically up the ladder.
        self._position = max(self._position, self._index(strategy))
        nxt = self._advance()
        if nxt is None:
            self._last_action = "STOP"
            return self._decision("STOP", "escalation ladder exhausted",
                                  ok=False)
        self._last_action = nxt
        return self._decision(nxt, "reduce uncertainty", ok=True)

    def state(self) -> Dict[str, Any]:
        return {
            "position": self._position,
            "current_strategy": self.current_strategy(),
            "direct_guess_failures": self._direct_guess_failures,
            "guess_budget": self._budget,
            "forced": self._forced,
            "last_action": self._last_action,
            "history": list(self._history),
            "ladder": list(self._ladder),
        }

    def exhausted(self) -> bool:
        return self._position >= len(self._ladder) - 1

    # -- internals ----------------------------------------------------------
    def _index(self, strategy: str) -> int:
        try:
            return self._ladder.index(strategy)
        except ValueError:
            return 0

    def _advance(self) -> Optional[str]:
        if self._position < len(self._ladder) - 1:
            self._position += 1
            return self.current_strategy()
        return None

    def _force_enumeration(self) -> None:
        self._forced = True
        enum_idx = self._index("FILESYSTEM_ENUMERATION")
        self._position = max(self._position, enum_idx)

    @staticmethod
    def _decision(action: str, reason: str, *, ok: bool) -> GovernorDecision:
        return GovernorDecision(action=action, reason=reason, ok=ok)
