"""Action-loop detection for governed execution streams.

Re-authored pattern (NOT vendored) inspired by the repetition detector in
Liquid4All/antidoom, which finds loops in a token stream. Here it runs over a
stream of (tool, args_digest, state_digest) execution steps instead of decoded
tokens. CAPT addition: the post-step state digest is part of the cycle key, so
a repeat only counts as a loop when the system returns to the same state each
cycle; a retry that advances state forms a different cycle and is treated as
progress, not a loop.

Pure and deterministic: no model calls, halts nothing, mutates no runtime
state. Returns a typed StopLoopDetected a caller (run loop / flight recorder)
may act on. Status: source present + unit-tested; NOT yet integrated into the
live execution loop.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple


@dataclass(frozen=True)
class ActionStep:
    tool: str
    args_digest: str
    state_digest: str


@dataclass(frozen=True)
class StopLoopDetected:
    period: int
    repeats: int
    first_index: int


CycleKey = Tuple[Tuple[str, str, str], ...]


def _cycle_key(steps: Sequence[ActionStep]) -> CycleKey:
    return tuple((s.tool, s.args_digest, s.state_digest) for s in steps)


def detect_action_loop(
    steps: Sequence[ActionStep],
    *,
    min_period: int = 1,
    max_period: int = 16,
    min_repeats: int = 3,
) -> StopLoopDetected | None:
    """Return the shortest no-progress loop ending at the tail of ``steps``.

    A loop of period ``p`` is present when the final ``p * min_repeats`` steps
    form ``min_repeats`` identical consecutive cycles, where a cycle's identity
    includes each step's post-step ``state_digest``. Equal state digests across
    cycles mean the system returned to the same state (no progress). The repeat
    count is then extended backward while earlier cycles stay identical. The
    shortest qualifying period wins. Returns ``None`` when no loop is found.
    """
    n = len(steps)
    if n == 0 or min_repeats < 1:
        return None
    hi = min(max_period, n // min_repeats)
    for p in range(max(min_period, 1), hi + 1):
        window = p * min_repeats
        if window > n:
            break
        tail = steps[n - window:]
        base = _cycle_key(tail[:p])
        if any(_cycle_key(tail[i * p:(i + 1) * p]) != base for i in range(1, min_repeats)):
            continue
        repeats = min_repeats
        idx = n - window - p
        while idx >= 0 and _cycle_key(steps[idx:idx + p]) == base:
            repeats += 1
            idx -= p
        return StopLoopDetected(period=p, repeats=repeats, first_index=n - repeats * p)
    return None
