import pytest

from capt_runtime.cohort import (
    BoundedCohort, Contribution, ContributionOutcome, DeliberationEpoch,
    EscalationCategory, ParticipantCursor, cognitive_debt,
)


def test_stale_epoch_contribution_is_preserved_but_not_currently_admissible():
    epoch = DeliberationEpoch("m", "t")
    old = Contribution("critic", epoch.epoch, ContributionOutcome.CONTRIBUTE, 3)
    epoch.steer()
    assert old.admissible_current(epoch) is False
    fresh = Contribution("critic", epoch.epoch, ContributionOutcome.CONTRIBUTE, 4)
    assert fresh.admissible_current(epoch) is True


@pytest.mark.parametrize("outcome", [ContributionOutcome.FAILED, ContributionOutcome.UNAVAILABLE, ContributionOutcome.TIMED_OUT, ContributionOutcome.INDETERMINATE])
def test_failure_classes_never_count_as_current_contribution_or_pass(outcome):
    epoch = DeliberationEpoch("m", "t")
    contribution = Contribution("reviewer", 0, outcome, 1)
    assert contribution.admissible_current(epoch) is False


def test_cursor_delivers_only_unseen_authoritative_sequence_and_never_regresses():
    cursor = ParticipantCursor("reviewer", 4)
    assert [e["sequence"] for e in cursor.delta([{"sequence": 3}, {"sequence": 5}, {"sequence": 6}])] == [5, 6]
    cursor.consume_through(6)
    with pytest.raises(ValueError, match="CURSOR_CANNOT_REGRESS"):
        cursor.consume_through(5)


def test_silence_quorum_requires_all_required_pass_and_no_material_dissent_or_escalation():
    epoch = DeliberationEpoch("m", "t")
    cohort = BoundedCohort({"planner", "critic"}, 2, 2)
    cohort.record(Contribution("planner", 0, ContributionOutcome.PASS, 1))
    cohort.record(Contribution("critic", 0, ContributionOutcome.DISSENT, 1, material=True))
    assert cohort.stopping_reason(epoch) is None
    cohort.record(Contribution("critic", 0, ContributionOutcome.PASS, 2))
    assert cohort.stopping_reason(epoch) is None
    clean = BoundedCohort({"planner", "critic"}, 2, 2)
    clean.record(Contribution("planner", 0, ContributionOutcome.PASS, 1))
    clean.record(Contribution("critic", 0, ContributionOutcome.PASS, 1))
    assert clean.stopping_reason(epoch) == "SILENCE_QUORUM"


def test_escalation_and_evidence_debt_are_typed_and_visible():
    debt = cognitive_debt([
        Contribution("safety", 0, ContributionOutcome.ESCALATE, 1, escalation=EscalationCategory.SAFETY_BOUNDARY),
        Contribution("verifier", 0, ContributionOutcome.REQUEST_EVIDENCE, 1),
    ])
    assert debt == {"unresolvedDissent": 0, "unresolvedEscalation": 1, "requestedEvidence": 1, "staleResults": 0}
