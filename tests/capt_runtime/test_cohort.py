import pytest

from capt_runtime.cohort import (
    BoundedCohort, Contribution, ContributionOutcome, DeliberationEpoch,
    EscalationCategory, ParticipantCursor, cognitive_debt,
)


def c(participant, outcome, *, epoch=0, cursor=1, round=0, material=False, escalation=None, contribution_id=None):
    cid = contribution_id or "con-%s-%s-%s-%s-%s" % (participant, epoch, round, cursor, outcome.value)
    return Contribution(cid, participant, epoch, round, outcome, cursor, material=material, escalation=escalation)


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


def test_roster_and_bounds_fail_closed_at_construction():
    BoundedCohort({"planner"}, {"planner"}, 1, 2)
    with pytest.raises(ValueError, match="COHORT_REQUIRED_NOT_IN_ROSTER"):
        BoundedCohort({"planner", "critic"}, {"planner"}, 2, 2)
    with pytest.raises(ValueError, match="COHORT_PARTICIPANT_CAP"):
        BoundedCohort({"planner"}, {"planner", "critic"}, 1, 2)
    with pytest.raises(ValueError, match="COHORT_REQUIRED_EMPTY"):
        BoundedCohort(set(), {"observer"}, 1, 2)
    with pytest.raises(ValueError, match="COHORT_ROUND_CAP_INVALID"):
        BoundedCohort({"planner"}, {"planner"}, 1, 0)


def test_unknown_future_round_and_duplicate_contributions_fail_closed():
    cohort = BoundedCohort({"planner"}, {"planner"}, 1, 2)
    first = c("planner", ContributionOutcome.PASS)
    cohort.record(first)
    with pytest.raises(ValueError, match="COHORT_PARTICIPANT_NOT_ADMITTED"):
        cohort.record(c("intruder", ContributionOutcome.CONTRIBUTE))
    with pytest.raises(ValueError, match="COHORT_FUTURE_ROUND_CONTRIBUTION"):
        cohort.record(c("planner", ContributionOutcome.PASS, round=1))
    with pytest.raises(ValueError, match="COHORT_DUPLICATE_CONTRIBUTION"):
        cohort.record(first)


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


def test_silence_quorum_is_current_round_only_and_cap_does_not_mask_success():
    epoch = DeliberationEpoch("m", "t")
    cohort = BoundedCohort({"planner", "critic"}, {"planner", "critic"}, 2, 2)
    cohort.record(c("planner", ContributionOutcome.PASS, round=0, cursor=1))
    cohort.record(c("critic", ContributionOutcome.CONTRIBUTE, round=0, cursor=1))
    assert cohort.stopping_reason(epoch) is None
    cohort.next_round()
    cohort.record(c("critic", ContributionOutcome.PASS, round=1, cursor=2))
    # Planner's old round-0 PASS cannot satisfy round 1.
    assert cohort.stopping_reason(epoch) == "BOUNDED_INCOMPLETE"

    success = BoundedCohort({"planner", "critic"}, {"planner", "critic"}, 2, 2)
    success.next_round()
    success.record(c("planner", ContributionOutcome.PASS, round=1, cursor=2))
    success.record(c("critic", ContributionOutcome.PASS, round=1, cursor=2))
    # Reaching the cap must not mask a valid all-PASS result in the final round.
    assert success.stopping_reason(epoch) == "SILENCE_QUORUM"
    with pytest.raises(ValueError, match="COHORT_ROUND_CAP"):
        success.next_round()


def test_admitted_optional_participant_debt_is_material_under_contract_a():
    """Required controls PASS quorum; every admitted participant may block."""
    epoch = DeliberationEpoch("m", "t")
    cohort = BoundedCohort({"planner", "critic"}, {"planner", "critic", "watchdog"}, 3, 2)
    cohort.record(c("planner", ContributionOutcome.PASS))
    cohort.record(c("critic", ContributionOutcome.PASS))
    cohort.record(c("watchdog", ContributionOutcome.ESCALATE, escalation=EscalationCategory.SAFETY_BOUNDARY))
    assert cohort.stopping_reason(epoch) is None


def test_admitted_optional_participant_without_debt_does_not_block_quorum():
    epoch = DeliberationEpoch("m", "t")
    cohort = BoundedCohort({"planner", "critic"}, {"planner", "critic", "watchdog"}, 3, 2)
    cohort.record(c("planner", ContributionOutcome.PASS))
    cohort.record(c("critic", ContributionOutcome.PASS))
    cohort.record(c("watchdog", ContributionOutcome.CONTRIBUTE))
    assert cohort.stopping_reason(epoch) == "SILENCE_QUORUM"


def test_material_debt_at_final_round_closes_bounded_incomplete():
    epoch = DeliberationEpoch("m", "t")
    cohort = BoundedCohort({"planner"}, {"planner"}, 1, 2)
    cohort.record(c("planner", ContributionOutcome.DISSENT, material=True, round=0))
    cohort.next_round()
    cohort.record(c("planner", ContributionOutcome.PASS, round=1, cursor=2))
    assert cohort.stopping_reason(epoch) == "BOUNDED_INCOMPLETE"


def test_latest_contribution_in_round_controls_pass_state():
    epoch = DeliberationEpoch("m", "t")
    cohort = BoundedCohort({"planner"}, {"planner"}, 1, 2)
    cohort.record(c("planner", ContributionOutcome.PASS, cursor=1))
    cohort.record(c("planner", ContributionOutcome.CONTRIBUTE, cursor=2))
    assert cohort.stopping_reason(epoch) is None
    cohort.record(c("planner", ContributionOutcome.PASS, cursor=3))
    assert cohort.stopping_reason(epoch) == "SILENCE_QUORUM"


def test_escalation_category_is_structurally_tied_to_escalate_outcome():
    c("safety", ContributionOutcome.ESCALATE, escalation=EscalationCategory.SAFETY_BOUNDARY)
    with pytest.raises(ValueError, match="COHORT_ESCALATION_CATEGORY_REQUIRED"):
        c("safety", ContributionOutcome.ESCALATE)
    with pytest.raises(ValueError, match="COHORT_ESCALATION_CATEGORY_WITHOUT_ESCALATE"):
        c("safety", ContributionOutcome.PASS, escalation=EscalationCategory.SAFETY_BOUNDARY)


def test_cognitive_debt_is_epoch_aware_and_counts_stale_results():
    values = [
        c("critic", ContributionOutcome.DISSENT, epoch=0, material=True),
        c("safety", ContributionOutcome.ESCALATE, epoch=1, escalation=EscalationCategory.SAFETY_BOUNDARY),
        c("verifier", ContributionOutcome.REQUEST_EVIDENCE, epoch=1),
    ]
    assert cognitive_debt(values, current_epoch=1) == {
        "unresolvedDissent": 0,
        "unresolvedEscalation": 1,
        "requestedEvidence": 1,
        "staleResults": 1,
    }


def test_text_cohort_preserves_and_compiles_strict_v2_charter_policy():
    from capt_runtime.cohort_contract import compile_cohort_objective, normalize_cohort_spec

    raw = {
        "cohortId": "deepseek0731",
        "vesselsPerCohort": 44,
        "configurationId": "deep-charter-r2",
        "vesselCharterPolicy": {"schemaVersion": "2.0.0"},
    }
    normalized = normalize_cohort_spec(raw)
    policy = normalized["vesselCharterPolicy"]
    assert policy["schemaVersion"] == "2.0.0"
    assert policy["strictLedger"] is True
    assert policy["candidateMultiplier"] == 3
    assert policy["candidateRequiredFields"] == ["AXIS", "MECH", "FALSIFIER", "DELTA"]
    assert policy["requiredFields"] == [
        "SOURCE", "WHO", "WHAT", "WHY", "HOW", "AGAINST",
        "BIAS", "EVIDENCE", "INTERACTIONS", "FALSIFIER", "DELTA",
    ]
    text = compile_cohort_objective(
        "Review the target deeply.",
        provider="openrouter",
        model="deepseek/deepseek-v4-flash-0731",
        cohort_spec=raw,
    )
    assert "CAPT deep Vessel Charter contract v2:" in text
    assert "at least 132 surviving candidate charters" in text
    assert "CAPT_CANDIDATE C0001" in text
    assert "CAPT_VESSEL deepseek0731-vNNNN" in text


def test_v2_charter_accepts_cn_candidate_id_alias_with_lint():
    from capt_runtime.vessel_charter import validate_vessel_text

    spec = {
        "cohortId": "alias",
        "vesselsPerCohort": 1,
        "configurationId": "high",
        "vesselCharterPolicy": {
            "schemaVersion": "2.0.0",
            "candidateMultiplier": 2,
            "candidateMaxWords": 48,
        },
    }
    text = """CAPT_CANDIDATE CN0001 | AXIS=graph-neighborhood | MECH=widen cosine neighborhood to forty peers | FALSIFIER=score unchanged across noisy subsets | DELTA=test graph smoothing
CAPT_CANDIDATE CN0002 | AXIS=merge-threshold | MECH=lower agglomerative branch threshold to point ten | FALSIFIER=cluster fragmentation rises on short text | DELTA=test finer partitioning
CAPT_CHARTER_AUDIT | candidates=2 | selected=1 | expansion_rounds=1
CAPT_VESSEL alias-v0001 | SOURCE=CN0001 | WHO=w | WHAT=x | WHY=y | HOW=h | AGAINST=a | BIAS=b | EVIDENCE=e | INTERACTIONS=i | FALSIFIER=f | DELTA=d
"""
    result = validate_vessel_text(text, spec)
    assert result["valid"] is True
    assert result["observedCandidateCount"] == 2
    assert result["selectedSources"]["alias-v0001"] == "C0001"
    assert result["formatLintCount"] >= 2


def test_v2_contract_uses_unambiguous_canonical_candidate_ids():
    from capt_runtime.cohort_contract import compile_cohort_objective

    spec = {
        "cohortId": "canonical",
        "vesselsPerCohort": 2,
        "configurationId": "high",
        "vesselCharterPolicy": {"schemaVersion": "2.0.0"},
    }
    out = compile_cohort_objective(
        "Analyze.",
        provider="openrouter",
        model="test/model",
        cohort_spec=spec,
    )
    assert "CAPT_CANDIDATE C0001" in out
    assert "SOURCE=C0001" in out
    assert "CNNNN" not in out
    assert "physical_candidate_row_count" in out



def test_opaque_configuration_id_never_selects_reasoning_effort():
    from capt_runtime.reasoning import legacy_cohort_configuration_reasoning_effort
    assert legacy_cohort_configuration_reasoning_effort("ouro-repair-v1") == ""
    assert legacy_cohort_configuration_reasoning_effort("deep-charter-r2") == ""
    assert legacy_cohort_configuration_reasoning_effort("default") == ""
    assert legacy_cohort_configuration_reasoning_effort("high") == "high"
    assert legacy_cohort_configuration_reasoning_effort("max") == "xhigh"
    assert legacy_cohort_configuration_reasoning_effort(None) == ""
