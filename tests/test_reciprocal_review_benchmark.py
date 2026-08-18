"""CAPT-UPG-020 benchmark scorer tests."""

import pytest

from benchmarks.reciprocal_review import score_trials


def _trial(trial_id, mode, defect, flagged, **extra):
    row = {"trialId": trial_id, "mode": mode, "defectPresent": defect, "flagged": flagged}
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
    assert result["allRequiredModesPopulated"] is False


def test_independent_review_requires_separate_identities():
    trial = _trial(
        "i1", "independent_reviewer", True, True,
        generatorIdentity="model-a", reviewerIdentity="model-a",
    )
    with pytest.raises(ValueError, match="must differ"):
        score_trials([trial])


def test_verification_modes_require_explicit_domain():
    trial = _trial("v1", "deterministic_verification", True, True)
    with pytest.raises(ValueError, match="verificationDomain"):
        score_trials([trial])


def test_all_five_modes_can_be_compared_without_inventing_winner():
    trials = [
        _trial("s", "self_review", True, False),
        _trial("n", "naive_agreement", True, True),
        _trial("i", "independent_reviewer", True, True, generatorIdentity="a", reviewerIdentity="b"),
        _trial("d", "deterministic_verification", True, True, verificationDomain="tests"),
        _trial("c", "reviewer_plus_verification", True, True, generatorIdentity="a", reviewerIdentity="b", verificationDomain="tests"),
    ]
    result = score_trials(trials)
    assert result["allRequiredModesPopulated"] is True
    assert set(result["populatedModes"]) == set(result["modes"])
    assert "winner" not in result
