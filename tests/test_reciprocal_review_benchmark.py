"""CAPT-UPG-020 benchmark scorer tests."""

import pytest

from benchmarks.reciprocal_review import score_trials


def _trial(trial_id, mode, defect, flagged, case_id=None, **extra):
    row = {
        "trialId": trial_id,
        "caseId": case_id or trial_id,
        "caseDigest": "sha256:case-%s" % (case_id or trial_id),
        "repeatId": extra.pop("repeatId", "rep-1"),
        "runId": "run-%s" % trial_id,
        "mode": mode,
        "defectPresent": defect,
        "flagged": flagged,
        "groundTruthRef": "ground-truth://%s" % (case_id or trial_id),
        "protocolRef": extra.pop("protocolRef", "protocol://upg020-v1"),
        "evidenceRef": "ledger://%s" % trial_id,
    }
    row.update(extra)
    return row


def test_scores_observed_trials_without_treating_consensus_as_verification():
    trials = [
        _trial("s1", "self_review", True, True),
        _trial("s2", "self_review", True, False),
        _trial("s3", "self_review", False, True),
        _trial("s4", "self_review", False, False),
    ]
    result = score_trials(trials)
    self_review = result["modes"]["self_review"]
    assert self_review["truePositives"] == 1
    assert self_review["falseNegatives"] == 1
    assert self_review["falsePositives"] == 1
    assert self_review["trueNegatives"] == 1
    assert self_review["precision"] == 0.5
    assert self_review["recall"] == 0.5
    assert self_review["f1"] == 0.5
    assert self_review["falseRejectionRate"] == 0.5
    assert result["consensusIsVerification"] is False
    assert result["comparisonEligible"] is False


def test_independent_review_requires_separate_identities():
    trial = _trial(
        "i1", "independent_reviewer", True, True,
        generatorIdentity="model-a", reviewerIdentity="model-a",
        reviewerBlindToGroundTruth=True, reviewerBlindToOtherModes=True, leakageCheckRef="proof://leakage",
    )
    with pytest.raises(ValueError, match="must differ"):
        score_trials([trial])


def test_verification_modes_require_explicit_domain_and_evidence_reference():
    with pytest.raises(ValueError, match="verificationDomain"):
        score_trials([_trial("v1", "deterministic_verification", True, True)])
    trial = _trial(
        "v2", "deterministic_verification", True, True,
        verificationDomain="tests", verificationRef="",
    )
    with pytest.raises(ValueError, match="verificationRef"):
        score_trials([trial])


def test_duplicate_trial_ids_fail_closed():
    trials = [
        _trial("dup", "self_review", True, True, case_id="c1"),
        _trial("dup", "self_review", False, False, case_id="c2"),
    ]
    with pytest.raises(ValueError, match="duplicate trialId"):
        score_trials(trials)


def test_missing_evidence_ref_fails_closed():
    trial = _trial("s1", "self_review", True, True)
    trial.pop("evidenceRef")
    with pytest.raises(ValueError, match="evidenceRef"):
        score_trials([trial])



def test_case_fingerprint_must_match_across_modes():
    trials = [
        _trial("s", "self_review", True, True, case_id="case-1", caseDigest="sha256:a"),
        _trial("n", "naive_agreement", False, False, case_id="case-1", caseDigest="sha256:b"),
    ]
    with pytest.raises(ValueError, match="case fingerprint mismatch"):
        score_trials(trials)


def test_ground_truth_reference_is_required():
    trial = _trial("s1", "self_review", True, True)
    trial["groundTruthRef"] = ""
    with pytest.raises(ValueError, match="groundTruthRef"):
        score_trials([trial])


def test_unrecorded_optional_metrics_are_not_coerced_to_zero():
    result = score_trials([_trial("s1", "self_review", True, True)])
    mode = result["modes"]["self_review"]
    assert mode["meanTokens"] is None
    assert mode["meanCostUsd"] is None
    assert mode["meanLatencyMs"] is None
    assert mode["recordedTokensCount"] == 0


def test_zero_denominator_metrics_are_unknown_not_measured_zero():
    result = score_trials([_trial("s1", "self_review", True, True)])
    mode = result["modes"]["self_review"]
    assert mode["precision"] == 1.0
    assert mode["recall"] == 1.0
    assert mode["falseRejectionRate"] is None


def test_all_modes_require_same_case_set_for_comparison_eligibility():
    common = dict(generatorIdentity="generator-a")
    trials = [
        _trial("s", "self_review", True, False, case_id="case-a", **common),
        _trial("n", "naive_agreement", True, True, case_id="case-b", **common),
        _trial("i", "independent_reviewer", True, True, case_id="case-a", generatorIdentity="a", reviewerIdentity="b", reviewerBlindToGroundTruth=True, reviewerBlindToOtherModes=True, leakageCheckRef="proof://leakage"),
        _trial("d", "deterministic_verification", True, True, case_id="case-a", verificationDomain="tests", verificationRef="proof://d"),
        _trial("c", "reviewer_plus_verification", True, True, case_id="case-a", generatorIdentity="a", reviewerIdentity="b", reviewerBlindToGroundTruth=True, reviewerBlindToOtherModes=True, leakageCheckRef="proof://leakage", verificationDomain="tests", verificationRef="proof://c"),
    ]
    result = score_trials(trials)
    assert result["allRequiredModesPopulated"] is True
    assert result["comparableCaseSetAndRepeats"] is False
    assert result["comparisonEligible"] is False


def test_all_five_modes_can_be_compared_without_inventing_winner():
    trials = [
        _trial("s", "self_review", True, False, case_id="case-1"),
        _trial("n", "naive_agreement", True, True, case_id="case-1"),
        _trial("i", "independent_reviewer", True, True, case_id="case-1", generatorIdentity="a", reviewerIdentity="b", reviewerBlindToGroundTruth=True, reviewerBlindToOtherModes=True, leakageCheckRef="proof://leakage"),
        _trial("d", "deterministic_verification", True, True, case_id="case-1", verificationDomain="tests", verificationRef="proof://d"),
        _trial("c", "reviewer_plus_verification", True, True, case_id="case-1", generatorIdentity="a", reviewerIdentity="b", reviewerBlindToGroundTruth=True, reviewerBlindToOtherModes=True, leakageCheckRef="proof://leakage", verificationDomain="tests", verificationRef="proof://c"),
    ]
    result = score_trials(trials)
    assert result["allRequiredModesPopulated"] is True
    assert result["comparableCaseSetAndRepeats"] is True
    assert result["comparisonEligible"] is True
    assert result["empiricalInferenceEligible"] is False
    assert set(result["populatedModes"]) == set(result["modes"])
    assert "winner" not in result


def test_independent_review_requires_explicit_blinding_and_leakage_evidence():
    trial = _trial(
        "i-blind", "independent_reviewer", True, True,
        generatorIdentity="model-a", reviewerIdentity="model-b",
    )
    with pytest.raises(ValueError, match="reviewerBlindToGroundTruth"):
        score_trials([trial])


def test_protocol_mismatch_fails_closed():
    trials = [
        _trial("s", "self_review", True, True, case_id="case-1", protocolRef="protocol://a"),
        _trial("n", "naive_agreement", True, True, case_id="case-1", protocolRef="protocol://b"),
    ]
    with pytest.raises(ValueError, match="one protocolRef"):
        score_trials(trials)


def test_comparison_requires_matching_case_repeat_observations():
    trials = [
        _trial("s", "self_review", True, True, case_id="case-1", repeatId="rep-1"),
        _trial("n", "naive_agreement", True, True, case_id="case-1", repeatId="rep-2"),
        _trial("i", "independent_reviewer", True, True, case_id="case-1", repeatId="rep-1", generatorIdentity="a", reviewerIdentity="b", reviewerBlindToGroundTruth=True, reviewerBlindToOtherModes=True, leakageCheckRef="proof://leakage"),
        _trial("d", "deterministic_verification", True, True, case_id="case-1", repeatId="rep-1", verificationDomain="tests", verificationRef="proof://d"),
        _trial("c", "reviewer_plus_verification", True, True, case_id="case-1", repeatId="rep-1", generatorIdentity="a", reviewerIdentity="b", reviewerBlindToGroundTruth=True, reviewerBlindToOtherModes=True, leakageCheckRef="proof://leakage", verificationDomain="tests", verificationRef="proof://c"),
    ]
    result = score_trials(trials)
    assert result["comparisonEligible"] is False


def test_balanced_repeated_observations_expose_variance_and_inference_eligibility():
    trials = []
    for repeat_id in ("rep-1", "rep-2"):
        for case_id, defect in (("defect", True), ("clean", False)):
            trials.extend([
                _trial(f"s-{repeat_id}-{case_id}", "self_review", defect, defect, case_id=case_id, repeatId=repeat_id),
                _trial(f"n-{repeat_id}-{case_id}", "naive_agreement", defect, defect, case_id=case_id, repeatId=repeat_id),
                _trial(f"i-{repeat_id}-{case_id}", "independent_reviewer", defect, defect, case_id=case_id, repeatId=repeat_id, generatorIdentity="a", reviewerIdentity="b", reviewerBlindToGroundTruth=True, reviewerBlindToOtherModes=True, leakageCheckRef="proof://leakage"),
                _trial(f"d-{repeat_id}-{case_id}", "deterministic_verification", defect, defect, case_id=case_id, repeatId=repeat_id, verificationDomain="tests", verificationRef="proof://d"),
                _trial(f"c-{repeat_id}-{case_id}", "reviewer_plus_verification", defect, defect, case_id=case_id, repeatId=repeat_id, generatorIdentity="a", reviewerIdentity="b", reviewerBlindToGroundTruth=True, reviewerBlindToOtherModes=True, leakageCheckRef="proof://leakage", verificationDomain="tests", verificationRef="proof://c"),
            ])
    result = score_trials(trials)
    assert result["comparisonEligible"] is True
    assert result["classBalancePresent"] is True
    assert result["repeatedRunsPresent"] is True
    assert result["blindingControlsSatisfied"] is True
    assert result["empiricalInferenceEligible"] is True
    assert result["claimStatus"] == "empirical_inference_eligible"
    assert result["modes"]["self_review"]["replicateVariance"]["recall"]["populationStdDev"] == 0.0
