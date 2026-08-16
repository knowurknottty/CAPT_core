import pytest

from capt_runtime.cohort import (
    BoundedCohort, Contribution, ContributionOutcome, DeliberationEpoch,
    EscalationCategory, ParticipantCursor, cognitive_debt,
)


def c(participant, outcome, *, epoch=0, cursor=1, round=0, material=False, escalation=None):
    return Contribution("con-%s-%s-%s" % (participant, epoch, round), participant, epoch, round, outcome, cursor, material=material, escalation=escalation)


def test_stale_epoch_contribution_is_preserved_but_not_currently_admissible():
    epoch = DeliberationEpoch("m", "t")
    old = c("critic", ContributionOutcome.CONTRIBUTE)
    epoch.steer()
    assert old.admissible_current(epoch) is False
    assert c("critic", ContributionOutcome.CONTRIBUTE, epoch=1).admissible_current(epoch) is True


@pytest.mark.parametrize("outcome", [ContributionOutcome.FAILED, ContributionOutcome.UNAVAILABLE, ContributionOutcome.TIMED_OUT, ContributionOutcome.INDETERMINATE])
def test_failure_classes_never_count_as_current_contribution_or_pass(outcome):
    assert c("reviewer", outcome).admissible_current(DeliberationEpoch("m", "t")) is False


def test_cursor_consumes_real_event_envelope_global_sequence_and_never_regresses():
    cursor = ParticipantCursor("reviewer", 4)
    assert [e["globalSequence"] for e in cursor.delta([{"globalSequence": 3}, {"globalSequence": 5}, {"globalSequence": 6}])] == [5, 6]
    cursor.consume_through(6)
    with pytest.raises(ValueError, match="CURSOR_CANNOT_REGRESS"):
        cursor.consume_through(5)


def test_roster_is_real_cap_and_unknown_contributor_fails_closed():
    cohort = BoundedCohort({"planner"}, {"planner"}, 1, 2)
    cohort.record(c("planner", ContributionOutcome.PASS))
    with pytest.raises(ValueError, match="COHORT_PARTICIPANT_NOT_ADMITTED"):
        cohort.record(c("intruder", ContributionOutcome.CONTRIBUTE))
    overfull = BoundedCohort({"planner"}, {"planner", "critic"}, 1, 2)
    with pytest.raises(ValueError, match="COHORT_PARTICIPANT_CAP"):
        overfull.record(c("planner", ContributionOutcome.PASS))


def test_silence_quorum_requires_all_required_pass_and_no_material_dissent():
    epoch = DeliberationEpoch("m", "t")
    cohort = BoundedCohort({"planner", "critic"}, {"planner", "critic"}, 2, 2)
    cohort.record(c("planner", ContributionOutcome.PASS))
    cohort.record(c("critic", ContributionOutcome.DISSENT, material=True))
    assert cohort.stopping_reason(epoch) is None
    clean = BoundedCohort({"planner", "critic"}, {"planner", "critic"}, 2, 2)
    clean.record(c("planner", ContributionOutcome.PASS))
    clean.record(c("critic", ContributionOutcome.PASS))
    assert clean.stopping_reason(epoch) == "SILENCE_QUORUM"


def test_escalation_and_evidence_debt_are_typed_and_visible():
    debt = cognitive_debt([c("safety", ContributionOutcome.ESCALATE, escalation=EscalationCategory.SAFETY_BOUNDARY), c("verifier", ContributionOutcome.REQUEST_EVIDENCE)])
    assert debt == {"unresolvedDissent": 0, "unresolvedEscalation": 1, "requestedEvidence": 1, "staleResults": 0}
