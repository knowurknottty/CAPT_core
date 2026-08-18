"""CAPT-UPG-014 tests for truthful claim-scoped epistemic projections."""

from capt_ui.operator.epistemics import project_claim_epistemic_state, project_epistemic_ladder


def test_verified_and_accepted_remain_distinct_domain_scoped_states():
    claim = {"claimId": "cl-1", "statement": "Artifact digest matches expected output.", "evidenceIds": ["ev-1"], "verificationStatus": "verified", "promotionState": "accepted"}
    verification = {"status": {"kind": "verified"}, "verificationDomain": "artifact_correctness", "committed": True, "advisory": False}
    item = project_claim_epistemic_state(claim, verification)
    assert item["stages"] == ["CLAIM_PROPOSED", "EVIDENCE_RECORDED", "VERIFIED:artifact_correctness", "CLAIM_ACCEPTED"]
    assert item["verificationProvenance"] == "COMMITTED_VERIFICATION"
    assert item["acceptedIsUniversalTruth"] is False


def test_contradiction_never_renders_as_accepted_or_verified():
    claim = {"claimId": "cl-2", "statement": "Mutation was absent.", "evidenceIds": ["ev-2"], "verificationStatus": "contradicted", "promotionState": "rejected"}
    verification = {"status": {"kind": "contradicted", "domain": "effect_occurrence"}, "committed": True}
    item = project_claim_epistemic_state(claim, verification)
    joined = " ".join(item["stages"])
    assert "CONTRADICTED:effect_occurrence" in joined
    assert "CLAIM_REJECTED" in joined
    assert "CLAIM_ACCEPTED" not in joined
    assert "VERIFIED:effect_occurrence" not in joined


def test_advisory_observation_is_explicitly_not_committed_verification():
    claim = {"claimId": "cl-3", "statement": "Provider returned candidate text.", "evidenceIds": [], "verificationStatus": None, "promotionState": "proposed"}
    verification = {"status": {"kind": "observed_unverified"}, "domain": "provider_output", "committed": False, "advisory": True}
    item = project_claim_epistemic_state(claim, verification)
    assert "OBSERVED_UNVERIFIED:provider_output" in item["stages"]
    assert item["verificationProvenance"] == "ADVISORY_VERIFICATION"
    assert item["stages"][-1] == "CLAIM_PENDING"


def test_multiple_claims_stay_separate_and_stale_only_when_source_marks_stale():
    claims = [
        {"claimId": "a", "statement": "A", "evidenceIds": ["e1"], "promotionState": "accepted", "verificationStatus": "verified"},
        {"claimId": "b", "statement": "B", "evidenceIds": ["e2"], "promotionState": "qualified", "verificationStatus": "inconclusive"},
    ]
    ladder = project_epistemic_ladder(claims, {
        "a": {"status": {"kind": "verified"}, "domain": "claim_support", "committed": True},
        "b": {"status": {"kind": "inconclusive"}, "domain": "claim_support", "stale": True},
    })
    assert [item["claimId"] for item in ladder] == ["a", "b"]
    assert "STALE" not in ladder[0]["stages"]
    assert "STALE" in ladder[1]["stages"]
    assert "CLAIM_ACCEPTED" in ladder[0]["stages"]
    assert "CLAIM_QUALIFIED" in ladder[1]["stages"]
