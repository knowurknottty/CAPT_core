"""Bounded, non-authoritative CAPT cognitive coordination projections.

Cohort helpers preserve typed cognition and cursor state; RuntimeService/EventStore
remain responsible for authority, durability, evidence, and external execution.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Set

if TYPE_CHECKING:
    from capt_runtime.store import EventStore


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
    contribution_id: str
    participant: str
    epoch: int
    round: int
    outcome: ContributionOutcome
    cursor: int
    source_sequences: tuple[int, ...] = ()
    material: bool = False
    escalation: Optional[EscalationCategory] = None

    def __post_init__(self) -> None:
        if not self.contribution_id:
            raise ValueError("COHORT_CONTRIBUTION_ID_REQUIRED")
        if not self.participant:
            raise ValueError("COHORT_PARTICIPANT_REQUIRED")
        if self.epoch < 0 or self.round < 0 or self.cursor < 0:
            raise ValueError("COHORT_POSITION_NEGATIVE")
        if any(sequence < 0 for sequence in self.source_sequences):
            raise ValueError("COHORT_SOURCE_SEQUENCE_NEGATIVE")
        if self.outcome == ContributionOutcome.ESCALATE and self.escalation is None:
            raise ValueError("COHORT_ESCALATION_CATEGORY_REQUIRED")
        if self.outcome != ContributionOutcome.ESCALATE and self.escalation is not None:
            raise ValueError("COHORT_ESCALATION_CATEGORY_WITHOUT_ESCALATE")

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
        return [event for event in events if int(event["globalSequence"]) > self.last_sequence]

    def consume_through(self, sequence: int) -> None:
        if sequence < self.last_sequence:
            raise ValueError("CURSOR_CANNOT_REGRESS")
        self.last_sequence = sequence


@dataclass
class BoundedCohort:
    required: Set[str]
    roster: Set[str]
    participant_cap: int
    round_cap: int
    rounds: int = 0
    contributions: List[Contribution] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.participant_cap <= 0:
            raise ValueError("COHORT_PARTICIPANT_CAP_INVALID")
        if self.round_cap <= 0:
            raise ValueError("COHORT_ROUND_CAP_INVALID")
        if not self.required:
            raise ValueError("COHORT_REQUIRED_EMPTY")
        if not self.required <= self.roster:
            raise ValueError("COHORT_REQUIRED_NOT_IN_ROSTER")
        if len(self.roster) > self.participant_cap:
            raise ValueError("COHORT_PARTICIPANT_CAP")
        if self.rounds < 0 or self.rounds >= self.round_cap:
            raise ValueError("COHORT_ROUND_POSITION_INVALID")

    def record(self, contribution: Contribution) -> None:
        if contribution.participant not in self.roster:
            raise ValueError("COHORT_PARTICIPANT_NOT_ADMITTED")
        if contribution.round > self.rounds:
            raise ValueError("COHORT_FUTURE_ROUND_CONTRIBUTION")
        if any(c.contribution_id == contribution.contribution_id for c in self.contributions):
            raise ValueError("COHORT_DUPLICATE_CONTRIBUTION")
        self.contributions.append(contribution)

    def next_round(self) -> None:
        # `rounds` is the zero-based current round index. A cap of N therefore
        # permits rounds 0..N-1 and never creates an Nth index.
        if self.rounds + 1 >= self.round_cap:
            raise ValueError("COHORT_ROUND_CAP")
        self.rounds += 1

    def stopping_reason(self, epoch: DeliberationEpoch) -> Optional[str]:
        epoch_values = [c for c in self.contributions if c.epoch == epoch.epoch]
        has_escalation_debt = any(
            c.outcome in {ContributionOutcome.ESCALATE, ContributionOutcome.REQUEST_EVIDENCE}
            for c in epoch_values
        )
        has_material_dissent = any(
            c.outcome == ContributionOutcome.DISSENT and c.material for c in epoch_values
        )
        at_cap = self.rounds + 1 >= self.round_cap

        # Dissent/escalation/evidence debt cannot be erased merely by a later
        # PASS. At the final permitted round unresolved debt closes as bounded
        # incomplete rather than leaving an unbounded wait.
        if has_escalation_debt or has_material_dissent:
            return "BOUNDED_INCOMPLETE" if at_cap else None

        # Silence quorum is round-local: every required participant's latest
        # contribution in the current round must be PASS. A PASS from an older
        # round cannot satisfy a later round after new cognition occurred.
        latest: Dict[str, Contribution] = {}
        for contribution in epoch_values:
            if contribution.round == self.rounds:
                latest[contribution.participant] = contribution
        passed = {
            participant for participant, contribution in latest.items()
            if contribution.outcome == ContributionOutcome.PASS
        }
        if self.required <= passed:
            return "SILENCE_QUORUM"
        if at_cap:
            return "BOUNDED_INCOMPLETE"
        return None


def cognitive_debt(
    contributions: Iterable[Contribution], current_epoch: Optional[int] = None
) -> Dict[str, int]:
    values = list(contributions)
    if current_epoch is None:
        active = values
        stale_count = 0
    else:
        active = [c for c in values if c.epoch == current_epoch]
        stale_count = len(values) - len(active)
    return {
        "unresolvedDissent": sum(
            c.outcome == ContributionOutcome.DISSENT and c.material for c in active
        ),
        "unresolvedEscalation": sum(
            c.outcome == ContributionOutcome.ESCALATE for c in active
        ),
        "requestedEvidence": sum(
            c.outcome == ContributionOutcome.REQUEST_EVIDENCE for c in active
        ),
        "staleResults": stale_count,
    }


def persist_cohort_evidence(
    cohort_id: str,
    cohort: BoundedCohort,
    epoch: DeliberationEpoch,
    claim_id: str,
    store: EventStore,
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """Persist Cohort deliberation evidence into the authoritative EventStore claim stream."""
    import hashlib
    import json
    state = {
        "cohortId": cohort_id,
        "missionId": epoch.mission_id,
        "taskId": epoch.task_id,
        "epoch": epoch.epoch,
        "rounds": cohort.rounds,
        "roundCap": cohort.round_cap,
        "participantCap": cohort.participant_cap,
        "required": sorted(cohort.required),
        "roster": sorted(cohort.roster),
        "contributions": [
            {
                "contributionId": c.contribution_id,
                "participant": c.participant,
                "epoch": c.epoch,
                "round": c.round,
                "outcome": c.outcome.value,
                "cursor": c.cursor,
                "material": c.material,
                "escalation": c.escalation.value if c.escalation else None,
            }
            for c in cohort.contributions
        ],
        "stoppingReason": cohort.stopping_reason(epoch),
    }
    blob = json.dumps(state, sort_keys=True).encode()
    content_digest = "sha256:" + hashlib.sha256(blob).hexdigest()
    evidence = {
        "schemaVersion": "1.0.0",
        "evidenceId": "ev-cohort-" + cohort_id,
        "missionId": epoch.mission_id,
        "evidence": {
            "kind": "artifact_hash",
            "artifactPath": "/cohort/" + cohort_id,
            "artifactDigest": content_digest,
        },
        "collectedBy": {"actorId": metadata["actor"]["actorId"], "kind": metadata["actor"]["kind"]},
        "collectedAt": metadata["issuedAt"],
        "trust": "capt_authoritative",
    }
    from capt_runtime.services import RuntimeService
    svc = RuntimeService(store)
    svc.record_evidence(claim_id, evidence, metadata)
    return state


def load_cohort_state(cohort_id: str, store: EventStore) -> Optional[tuple[BoundedCohort, DeliberationEpoch]]:
    """Reconstruct BoundedCohort and DeliberationEpoch from durable SQLite EventStore state."""
    state = store.load_state("cohort-" + cohort_id)
    if state is None:
        return None
    cohort = BoundedCohort(
        required=set(state["required"]),
        roster=set(state["roster"]),
        participant_cap=state["participantCap"],
        round_cap=state["roundCap"],
        rounds=state["rounds"],
    )
    for cd in state.get("contributions", []):
        cohort.contributions.append(
            Contribution(
                contribution_id=cd["contributionId"],
                participant=cd["participant"],
                epoch=cd["epoch"],
                round=cd["round"],
                outcome=ContributionOutcome(cd["outcome"]),
                cursor=cd["cursor"],
                material=cd.get("material", False),
                escalation=EscalationCategory(cd["escalation"]) if cd.get("escalation") else None,
            )
        )
    epoch = DeliberationEpoch(mission_id=state["missionId"], task_id=state["taskId"], epoch=state["epoch"])
    return cohort, epoch
