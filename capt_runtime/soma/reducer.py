"""Minimal SOMA-compatible context reducer."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Protocol, Sequence, runtime_checkable

from .trajectory import CodingTrajectory, TrajectoryEvent


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()


def _sha256(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value)).hexdigest()


@dataclass(frozen=True)
class CompressionReceipt:
    policy_version: str
    budget_events: int
    input_digest: str
    retained_digest: str
    removed_digest: str
    digest: str


@runtime_checkable
class ReducerResult(Protocol):
    input_events: int
    output_events: int
    digest: str
    receipt: CompressionReceipt

    @property
    def events(self) -> Sequence[TrajectoryEvent]: ...


@dataclass(frozen=True)
class CompressedContext:
    retained: List[TrajectoryEvent]
    removed: List[Dict[str, Any]]
    input_events: int
    output_events: int
    receipt: CompressionReceipt

    @property
    def digest(self) -> str:
        return self.receipt.digest

    @property
    def events(self) -> Sequence[TrajectoryEvent]:
        return self.retained


class ContextReducer:
    """Deterministic reducer preserving high-value coding state."""

    POLICY_VERSION = "soma-context-reducer-v2"
    IMPORTANT = {
        "error", "failure", "test", "decision", "constraint",
        "interface", "api", "schema", "diff", "commit"
    }

    def compress(self, trajectory: CodingTrajectory, budget_events: int) -> CompressedContext:
        if isinstance(budget_events, bool) or not isinstance(budget_events, int):
            raise TypeError("budget_events must be an integer")
        if budget_events < 0 or budget_events > len(trajectory.events):
            raise ValueError("budget_events must be within [0, input_events]")

        scored = []
        for index, event in enumerate(trajectory.events):
            words = set(re.findall(r"[A-Za-z0-9_]+", event.content.lower()))
            exact_kind = 1 if event.kind.lower() in self.IMPORTANT else 0
            lexical_matches = len(words & self.IMPORTANT)
            role_bonus = 1 if event.metadata.get("role") in {"tool", "system"} else 0
            scored.append(
                (event.importance, exact_kind, lexical_matches, role_bonus, index, event)
            )

        kept = sorted(
            scored,
            key=lambda item: (-item[0], -item[1], -item[2], -item[3], item[4]),
        )[:budget_events]
        keep_ids = {index for _, _, _, _, index, _ in kept}
        retained = [event for index, event in enumerate(trajectory.events) if index in keep_ids]
        removed = [
            {"index": index, "event": event, "reason": "lower_information_score"}
            for index, event in enumerate(trajectory.events)
            if index not in keep_ids
        ]

        input_payload = [asdict(event) for event in trajectory.events]
        retained_payload = [asdict(event) for event in retained]
        removed_payload = [
            {"index": item["index"], "event": asdict(item["event"]), "reason": item["reason"]}
            for item in removed
        ]
        input_digest = _sha256(input_payload)
        retained_digest = _sha256(retained_payload)
        removed_digest = _sha256(removed_payload)
        receipt_payload = {
            "policy_version": self.POLICY_VERSION,
            "budget_events": budget_events,
            "input_digest": input_digest,
            "retained_digest": retained_digest,
            "removed_digest": removed_digest,
        }
        receipt = CompressionReceipt(
            policy_version=self.POLICY_VERSION,
            budget_events=budget_events,
            input_digest=input_digest,
            retained_digest=retained_digest,
            removed_digest=removed_digest,
            digest=_sha256(receipt_payload),
        )
        return CompressedContext(
            retained=retained,
            removed=removed,
            input_events=len(trajectory.events),
            output_events=len(retained),
            receipt=receipt,
        )
