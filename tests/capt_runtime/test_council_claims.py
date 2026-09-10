from __future__ import annotations

import pytest

from capt_runtime.council import (
    ClaimObservation,
    ClaimStance,
    ClaimStatus,
    CouncilTier,
    CouncilValidationError,
    analyze_claims,
    select_challenges,
)
from tests.capt_runtime.test_council_alpha import make_council


def obs(
    claim_id: str, cohort: str, vessel: str, stance: ClaimStance,
    *, confidence: float = 0.8, evidence: tuple[str, ...] = (), text: str = "claim A",
) -> ClaimObservation:
    return ClaimObservation(
        claim_id=claim_id, claim_text=text, cohort_id=cohort, vessel_id=vessel,
        stance=stance, confidence=confidence, evidence_ids=evidence,
    )

def test_dissent_survives_and_vessels_in_same_cohort_do_not_multiply_independence():
    council = make_council(CouncilTier.SMALL)
    analysis = analyze_claims(council, (
        obs("a", "c00", "c00-v0001", ClaimStance.SUPPORT),
        obs("a", "c00", "c00-v0002", ClaimStance.SUPPORT),
        obs("a", "c01", "c01-v0001", ClaimStance.DISSENT, confidence=0.9),
    ))
    claim = analysis.claims[0]
    assert claim.status == ClaimStatus.DISPUTED
    assert claim.support_cohorts == ("c00",)
    assert claim.dissent_cohorts == ("c01",)
    assert len(claim.support_vessels) == 2
    assert claim.verification_state == "unverified"
    assert len(analysis.raw_observations) == 3


def test_insufficient_evidence_remains_explicit_not_silently_dropped():
    council = make_council(CouncilTier.SMALL)
    analysis = analyze_claims(council, (
        obs("a", "c00", "c00-v0001", ClaimStance.INSUFFICIENT, confidence=0.2),
        obs("a", "c01", "c01-v0001", ClaimStance.INSUFFICIENT, confidence=0.3),
    ))
    claim = analysis.claims[0]
    assert claim.status == ClaimStatus.INSUFFICIENT
    assert claim.insufficient_cohorts == ("c00", "c01")

def test_convergence_collects_evidence_but_never_self_verifies():
    council = make_council(CouncilTier.SMALL)
    analysis = analyze_claims(council, (
        obs("a", "c00", "c00-v0001", ClaimStance.SUPPORT, evidence=("ev-1",)),
        obs("a", "c01", "c01-v0001", ClaimStance.SUPPORT, evidence=("ev-2",)),
    ))
    claim = analysis.claims[0]
    assert claim.status == ClaimStatus.CONVERGED
    assert claim.evidence_ids == ("ev-1", "ev-2")
    assert claim.verification_state == "unverified"


def test_material_dispute_becomes_targeted_challenge():
    council = make_council(CouncilTier.SMALL)
    analysis = analyze_claims(council, (
        obs("a", "c00", "c00-v0001", ClaimStance.SUPPORT, confidence=0.8),
        obs("a", "c01", "c01-v0001", ClaimStance.DISSENT, confidence=0.9),
    ))
    challenges = select_challenges(analysis)
    assert [(c.claim_id, c.reason) for c in challenges] == [("a", "material_dispute")]
    assert challenges[0].support_cohorts == ("c00",)
    assert challenges[0].dissent_cohorts == ("c01",)


def test_unanimous_claim_without_evidence_is_challenged_not_blindly_trusted():
    council = make_council(CouncilTier.SMALL)
    analysis = analyze_claims(council, (
        obs("a", "c00", "c00-v0001", ClaimStance.SUPPORT),
        obs("a", "c01", "c01-v0001", ClaimStance.SUPPORT),
    ))
    assert [c.reason for c in select_challenges(analysis)] == ["unsupported_unanimity"]

def test_high_confidence_minority_survives_and_is_challenged():
    council = make_council(CouncilTier.MEDIUM)
    analysis = analyze_claims(council, (
        obs("a", "c00", "c00-v0001", ClaimStance.SUPPORT, confidence=0.96, evidence=("ev-x",)),
        obs("a", "c01", "c01-v0001", ClaimStance.INSUFFICIENT, confidence=0.2),
        obs("a", "c02", "c02-v0001", ClaimStance.INSUFFICIENT, confidence=0.2),
        obs("a", "c03", "c03-v0001", ClaimStance.INSUFFICIENT, confidence=0.2),
    ))
    claim = analysis.claims[0]
    assert claim.status == ClaimStatus.MINORITY
    assert [c.reason for c in select_challenges(analysis)] == ["high_confidence_minority"]


def test_claim_text_mismatch_and_unknown_vessel_are_rejected():
    council = make_council(CouncilTier.SMALL)
    with pytest.raises(CouncilValidationError, match="CLAIM_TEXT_MISMATCH"):
        analyze_claims(council, (
            obs("a", "c00", "c00-v0001", ClaimStance.SUPPORT, text="one"),
            obs("a", "c01", "c01-v0001", ClaimStance.SUPPORT, text="two"),
        ))
    with pytest.raises(CouncilValidationError, match="UNKNOWN_VESSEL"):
        analyze_claims(council, (
            obs("a", "c00", "made-up", ClaimStance.SUPPORT),
        ))