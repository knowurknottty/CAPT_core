"""Minimal SOMA-compatible context reducer.

This intentionally does not replace CAPT memory. It extracts a deterministic
compression policy suitable for subnet benchmarking.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class CodingTrajectory:
    events: List[Dict[str, Any]]


@dataclass(frozen=True)
class CompressedContext:
    retained: List[Dict[str, Any]]
    removed: List[Dict[str, Any]]
    input_events: int
    output_events: int
    digest: str


class ContextReducer:
    """Deterministic reducer preserving high-value coding state.

    Priority is evidence preservation, not maximum compression.
    """

    IMPORTANT = {
        "error", "failure", "test", "decision", "constraint",
        "interface", "api", "schema", "diff", "commit"
    }

    def compress(self, trajectory: CodingTrajectory, budget_events: int) -> CompressedContext:
        scored = []
        for index, event in enumerate(trajectory.events):
            text = json.dumps(event, sort_keys=True).lower()
            score = sum(2 for token in self.IMPORTANT if token in text)
            score += 1 if event.get("role") in {"tool", "system"} else 0
            scored.append((score, index, event))

        kept = sorted(scored, key=lambda x: (-x[0], x[1]))[:budget_events]
        keep_ids = {idx for _, idx, _ in kept}
        retained = [event for idx, event in enumerate(trajectory.events) if idx in keep_ids]
        removed = [
            {"index": idx, "event": event, "reason": "lower_information_score"}
            for idx, event in enumerate(trajectory.events)
            if idx not in keep_ids
        ]
        payload = json.dumps(retained, sort_keys=True).encode()
        return CompressedContext(
            retained=retained,
            removed=removed,
            input_events=len(trajectory.events),
            output_events=len(retained),
            digest="sha256:" + hashlib.sha256(payload).hexdigest(),
        )
