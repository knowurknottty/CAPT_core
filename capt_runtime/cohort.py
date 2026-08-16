"""Bounded, non-authoritative CAPT cognitive coordination projections.

Cohort helpers preserve typed cognition and cursor state; RuntimeService/EventStore
remain responsible for authority, durability, evidence, and external execution.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, List, Optional, Set


class ContributionOutcome(str, Enum):
    CONTRIBUTE = "CONTRIBUTE"
    PASS = "PASS"
    DISSENT = "DISSENT"
    ESCALATE = "ESCALATE"
    REQUEST_EVIDENCE = "REQUEST_EVIDENCE"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"
    TIMED_OUT = "TIMED_OUT"
    INDETERMINATE = "INDETERMINATE"


class EscalationCategory(str, Enum):
    AUTHORITY_REQUIRED = "AUTHORITY_REQUIRED"
    VALUE_JUDGMENT = "VALUE_JUDGMENT"
    AMBIGUOUS_INTENT = "AMBIGUOUS_INTENT"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    IRREVERSIBLE_ACTION = "IRREVERSIBLE_ACTION"
    COST_APPROVAL = "COST_APPROVAL"
    CONFLICT_RESOLUTION = "CONFLICT_RESOLUTION"
    SAFETY_BOUNDARY = "SAFETY_BOUNDARY"


@dataclass
class DeliberationEpoch:
    mission_id: str
    task_id: str
    epoch: int = 0

    def steer(self) -> int:
        self.epoch += 1
        return self.epoch

    def is_current(self, contribution_epoch: int) -> bool:
        return contribution_epoch == self.epoch


@dataclass(frozen=True)
class Contribution:
    participant: str
    epoch: int
    outcome: ContributionOutcome
    cursor: int
    source_sequences: tuple[int, ...] = ()
    material: bool = False
    escalation: Optional[EscalationCategory] = None

    def admissible_current(self, deliberation: DeliberationEpoch) -> bool:
        return deliberation.is_current(self.epoch) and self.outcome not in {
            ContributionOutcome.FAILED, ContributionOutcome.UNAVAILABLE,
            ContributionOutcome.TIMED_OUT, ContributionOutcome.INDETERMINATE,
        }


@dataclass
class ParticipantCursor:
    participant: str
    last_sequence: int = 0

    def delta(self, events: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
        return [event for event in events if int(event["sequence"]) > self.last_sequence]

    def consume_through(self, sequence: int) -> None:
        if sequence < self.last_sequence:
            raise ValueError("CURSOR_CANNOT_REGRESS")
        self.last_sequence = sequence


@dataclass
class BoundedCohort:
    required: Set[str]
    participant_cap: int
    round_cap: int
    rounds: int = 0
    contributions: List[Contribution] = field(default_factory=list)

    def record(self, contribution: Contribution) -> None:
        if contribution.participant not in self.required and len(self.required) >= self.participant_cap:
            raise ValueError("COHORT_PARTICIPANT_CAP")
        self.contributions.append(contribution)

    def next_round(self) -> None:
        if self.rounds >= self.round_cap:
            raise ValueError("COHORT_ROUND_CAP")
        self.rounds += 1

    def stopping_reason(self, epoch: DeliberationEpoch) -> Optional[str]:
        if self.rounds >= self.round_cap:
            return "BOUNDED_INCOMPLETE"
        current = [c for c in self.contributions if c.epoch == epoch.epoch]
        if any(c.outcome in {ContributionOutcome.ESCALATE, ContributionOutcome.REQUEST_EVIDENCE} for c in current):
            return None
        if any(c.outcome == ContributionOutcome.DISSENT and c.material for c in current):
            return None
        passed = {c.participant for c in current if c.outcome == ContributionOutcome.PASS}
        if self.required <= passed:
            return "SILENCE_QUORUM"
        return None


def cognitive_debt(contributions: Iterable[Contribution]) -> Dict[str, int]:
    values = list(contributions)
    return {
        "unresolvedDissent": sum(c.outcome == ContributionOutcome.DISSENT and c.material for c in values),
        "unresolvedEscalation": sum(c.outcome == ContributionOutcome.ESCALATE for c in values),
        "requestedEvidence": sum(c.outcome == ContributionOutcome.REQUEST_EVIDENCE for c in values),
        "staleResults": 0,
    }
