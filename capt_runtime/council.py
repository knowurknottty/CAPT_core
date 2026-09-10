"""Governed Model Council alpha contracts and deterministic projections.

Council state is above existing Cohorts. This module is deliberately effect-free:
it defines topology, logical dispatch intent, launch interlocks, timing, and
structured epistemic analysis. External model execution remains a RuntimeService /
DriverRun responsibility.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Iterable, Mapping


MAX_DISTINCT_COHORTS = 24
MAX_VESSELS_PER_COHORT = 1000
MAX_LOGICAL_VESSELS = MAX_DISTINCT_COHORTS * MAX_VESSELS_PER_COHORT
EXTREME_DEFAULT_VESSELS_PER_COHORT = 18
DEFAULT_SYNTHESIS_POLICY = "independent_convergence_adversarial_adjudication"
DEFAULT_CHALLENGE_POLICY = "material_disagreement"


class CouncilValidationError(ValueError):
    """A Council definition or state transition violates the alpha contract."""


class CouncilTier(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    EXTREME = "extreme"


@dataclass(frozen=True)
class TierPreset:
    tier: CouncilTier
    cohort_count: int
    vessels_per_cohort: int

    @property
    def logical_vessels(self) -> int:
        return self.cohort_count * self.vessels_per_cohort

def tier_preset(
    tier: CouncilTier | str, *, vessels_per_cohort: int | None = None
) -> TierPreset:
    tier = CouncilTier(tier)
    fixed = {
        CouncilTier.SMALL: (2, 3),
        CouncilTier.MEDIUM: (4, 6),
        CouncilTier.LARGE: (12, 9),
    }
    if tier in fixed:
        cohorts, vessels = fixed[tier]
        if vessels_per_cohort is not None and int(vessels_per_cohort) != vessels:
            raise CouncilValidationError("FIXED_TIER_VESSEL_COUNT_MISMATCH")
        return TierPreset(tier, cohorts, vessels)

    vessels = (
        EXTREME_DEFAULT_VESSELS_PER_COHORT
        if vessels_per_cohort is None else int(vessels_per_cohort)
    )
    if not EXTREME_DEFAULT_VESSELS_PER_COHORT <= vessels <= MAX_VESSELS_PER_COHORT:
        raise CouncilValidationError("EXTREME_VESSEL_COUNT_RANGE")
    return TierPreset(tier, MAX_DISTINCT_COHORTS, vessels)


@dataclass(frozen=True)
class CohortDefinition:
    cohort_id: str
    provider_id: str
    model_id: str
    configuration_id: str = "default"


@dataclass(frozen=True)
class CouncilDefinition:
    council_id: str
    tier: CouncilTier
    cohorts: tuple[CohortDefinition, ...]
    vessels_per_cohort: int
    synthesis_policy: str = DEFAULT_SYNTHESIS_POLICY
    challenge_policy: str = DEFAULT_CHALLENGE_POLICY

    @property
    def logical_vessel_count(self) -> int:
        return len(self.cohorts) * self.vessels_per_cohort


@dataclass(frozen=True)
class VesselDispatchIntent:
    vessel_id: str
    cohort_id: str
    provider_id: str
    model_id: str
    configuration_id: str
    ordinal: int

def validate_council(definition: CouncilDefinition) -> None:
    if not definition.council_id.strip():
        raise CouncilValidationError("COUNCIL_ID_REQUIRED")
    preset = tier_preset(
        definition.tier, vessels_per_cohort=definition.vessels_per_cohort
    )
    if len(definition.cohorts) != preset.cohort_count:
        raise CouncilValidationError("COHORT_COUNT_MISMATCH")
    if definition.logical_vessel_count > MAX_LOGICAL_VESSELS:
        raise CouncilValidationError("MAX_LOGICAL_VESSELS")
    if not definition.synthesis_policy.strip():
        raise CouncilValidationError("SYNTHESIS_POLICY_REQUIRED")
    if not definition.challenge_policy.strip():
        raise CouncilValidationError("CHALLENGE_POLICY_REQUIRED")

    ids: set[str] = set()
    for cohort in definition.cohorts:
        values = (
            cohort.cohort_id, cohort.provider_id, cohort.model_id,
            cohort.configuration_id,
        )
        if any(not value.strip() for value in values):
            raise CouncilValidationError("COHORT_IDENTITY_REQUIRED")
        if cohort.cohort_id in ids:
            raise CouncilValidationError("DUPLICATE_COHORT_ID")
        ids.add(cohort.cohort_id)


def _canonical_material(definition: CouncilDefinition) -> dict[str, object]:
    validate_council(definition)
    return {
        "schemaVersion": "council-alpha-1",
        "councilId": definition.council_id,
        "tier": CouncilTier(definition.tier).value,
        "vesselsPerCohort": definition.vessels_per_cohort,
        "synthesisPolicy": definition.synthesis_policy,
        "challengePolicy": definition.challenge_policy,
        "cohorts": [
            {
                "cohortId": c.cohort_id, "providerId": c.provider_id,
                "modelId": c.model_id, "configurationId": c.configuration_id,
            }
            for c in sorted(definition.cohorts, key=lambda value: value.cohort_id)
        ],
    }

def council_digest(definition: CouncilDefinition) -> str:
    encoded = json.dumps(
        _canonical_material(definition), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def build_logical_blast(definition: CouncilDefinition) -> tuple[VesselDispatchIntent, ...]:
    """Expand the complete logical Vessel set before any transport admission."""
    validate_council(definition)
    intents: list[VesselDispatchIntent] = []
    for cohort in sorted(definition.cohorts, key=lambda value: value.cohort_id):
        for ordinal in range(1, definition.vessels_per_cohort + 1):
            intents.append(
                VesselDispatchIntent(
                    vessel_id=f"{cohort.cohort_id}-v{ordinal:04d}",
                    cohort_id=cohort.cohort_id,
                    provider_id=cohort.provider_id,
                    model_id=cohort.model_id,
                    configuration_id=cohort.configuration_id,
                    ordinal=ordinal,
                )
            )
    return tuple(intents)


@dataclass(frozen=True)
class CouncilLaunchAuthorization:
    council_digest: str
    extreme_ack: bool = False
    custom_scale_ack: bool = False
    maximum_spend_usd: Decimal | None = None


@dataclass(frozen=True)
class CouncilLaunchPreview:
    council_digest: str
    tier: CouncilTier
    cohort_count: int
    vessels_per_cohort: int
    logical_vessels: int
    requires_extreme_ack: bool
    requires_custom_scale_ack: bool
    maximum_spend_usd: Decimal | None

def launch_preview(
    definition: CouncilDefinition, authorization: CouncilLaunchAuthorization | None = None
) -> CouncilLaunchPreview:
    validate_council(definition)
    digest_value = council_digest(definition)
    is_extreme = CouncilTier(definition.tier) == CouncilTier.EXTREME
    custom_scale = is_extreme and (
        definition.vessels_per_cohort != EXTREME_DEFAULT_VESSELS_PER_COHORT
    )
    return CouncilLaunchPreview(
        council_digest=digest_value,
        tier=CouncilTier(definition.tier),
        cohort_count=len(definition.cohorts),
        vessels_per_cohort=definition.vessels_per_cohort,
        logical_vessels=definition.logical_vessel_count,
        requires_extreme_ack=is_extreme,
        requires_custom_scale_ack=custom_scale,
        maximum_spend_usd=(authorization.maximum_spend_usd if authorization else None),
    )


def authorize_launch(
    definition: CouncilDefinition, authorization: CouncilLaunchAuthorization
) -> CouncilLaunchPreview:
    preview = launch_preview(definition, authorization)
    if authorization.council_digest != preview.council_digest:
        if preview.requires_extreme_ack and not authorization.extreme_ack:
            raise CouncilValidationError("EXTREME_ACK_REQUIRED")
        raise CouncilValidationError("COUNCIL_DIGEST_MISMATCH")
    if preview.requires_extreme_ack and not authorization.extreme_ack:
        raise CouncilValidationError("EXTREME_ACK_REQUIRED")
    if preview.requires_custom_scale_ack and not authorization.custom_scale_ack:
        raise CouncilValidationError("CUSTOM_SCALE_ACK_REQUIRED")
    if authorization.maximum_spend_usd is not None and authorization.maximum_spend_usd < 0:
        raise CouncilValidationError("MAXIMUM_SPEND_NEGATIVE")
    return preview


def _parse_timestamp(value: str) -> datetime:
    if not value or not value.strip():
        raise CouncilValidationError("TIMESTAMP_REQUIRED")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CouncilValidationError("TIMESTAMP_INVALID") from exc

@dataclass(frozen=True)
class VesselTiming:
    logical_dispatched_at: str
    transport_admitted_at: str | None = None
    provider_started_at: str | None = None
    completed_at: str | None = None

    def __post_init__(self) -> None:
        _parse_timestamp(self.logical_dispatched_at)

    def _transition(self, field: str, timestamp: str, prior: str | None) -> "VesselTiming":
        current = getattr(self, field)
        if current is not None:
            raise CouncilValidationError("TIMING_TRANSITION_ALREADY_RECORDED")
        if prior is None:
            raise CouncilValidationError("TIMING_PREREQUISITE_MISSING")
        if _parse_timestamp(timestamp) < _parse_timestamp(prior):
            raise CouncilValidationError("TIMING_REGRESSION")
        return replace(self, **{field: timestamp})

    def admit_transport(self, timestamp: str) -> "VesselTiming":
        return self._transition(
            "transport_admitted_at", timestamp, self.logical_dispatched_at
        )

    def start_provider(self, timestamp: str) -> "VesselTiming":
        return self._transition(
            "provider_started_at", timestamp, self.transport_admitted_at
        )

    def complete(self, timestamp: str) -> "VesselTiming":
        return self._transition("completed_at", timestamp, self.provider_started_at)


class ClaimStance(str, Enum):
    SUPPORT = "support"
    DISSENT = "dissent"
    INSUFFICIENT = "insufficient_evidence"
    ABSTAIN = "abstain"


class ClaimStatus(str, Enum):
    CONVERGED = "converged"
    DISPUTED = "disputed"
    MINORITY = "minority"
    INSUFFICIENT = "insufficient_evidence"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class ClaimObservation:
    claim_id: str
    claim_text: str
    cohort_id: str
    vessel_id: str
    stance: ClaimStance
    confidence: float
    evidence_ids: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    uncertainty_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.claim_id.strip() or not self.claim_text.strip():
            raise CouncilValidationError("CLAIM_ID_AND_TEXT_REQUIRED")
        if not self.cohort_id.strip() or not self.vessel_id.strip():
            raise CouncilValidationError("OBSERVATION_SOURCE_REQUIRED")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise CouncilValidationError("CLAIM_CONFIDENCE_RANGE")

@dataclass(frozen=True)
class CouncilClaim:
    claim_id: str
    claim_text: str
    status: ClaimStatus
    support_cohorts: tuple[str, ...]
    dissent_cohorts: tuple[str, ...]
    insufficient_cohorts: tuple[str, ...]
    abstain_cohorts: tuple[str, ...]
    support_vessels: tuple[str, ...]
    dissent_vessels: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    assumptions: tuple[str, ...]
    max_support_confidence: float
    max_dissent_confidence: float
    verification_state: str = "unverified"


@dataclass(frozen=True)
class CouncilDispute:
    claim_id: str
    support_cohorts: tuple[str, ...]
    dissent_cohorts: tuple[str, ...]


@dataclass(frozen=True)
class CouncilAnalysis:
    council_digest: str
    cohort_count: int
    distinct_model_sources: int
    claims: tuple[CouncilClaim, ...]
    disputes: tuple[CouncilDispute, ...]
    raw_observations: tuple[ClaimObservation, ...]


@dataclass(frozen=True)
class CouncilChallenge:
    claim_id: str
    reason: str
    support_cohorts: tuple[str, ...]
    dissent_cohorts: tuple[str, ...]
    evidence_ids: tuple[str, ...]
def _claim_status(
    support: tuple[str, ...], dissent: tuple[str, ...],
    insufficient: tuple[str, ...], abstain: tuple[str, ...],
) -> ClaimStatus:
    if support and dissent:
        return ClaimStatus.DISPUTED
    if support:
        non_support = len(insufficient) + len(abstain)
        if non_support > len(support):
            return ClaimStatus.MINORITY
        return ClaimStatus.CONVERGED
    if insufficient and not dissent:
        return ClaimStatus.INSUFFICIENT
    return ClaimStatus.UNRESOLVED


def analyze_claims(
    definition: CouncilDefinition, observations: Iterable[ClaimObservation]
) -> CouncilAnalysis:
    validate_council(definition)
    raw = tuple(observations)
    vessel_map = {v.vessel_id: v for v in build_logical_blast(definition)}
    grouped: dict[str, list[ClaimObservation]] = {}
    for observation in raw:
        intent = vessel_map.get(observation.vessel_id)
        if intent is None:
            raise CouncilValidationError("UNKNOWN_VESSEL")
        if intent.cohort_id != observation.cohort_id:
            raise CouncilValidationError("VESSEL_COHORT_MISMATCH")
        grouped.setdefault(observation.claim_id, []).append(observation)

    claims: list[CouncilClaim] = []
    disputes: list[CouncilDispute] = []
    for claim_id in sorted(grouped):
        values = grouped[claim_id]
        texts = {value.claim_text for value in values}
        if len(texts) != 1:
            raise CouncilValidationError("CLAIM_TEXT_MISMATCH")
        support_cohorts = tuple(sorted({v.cohort_id for v in values if v.stance == ClaimStance.SUPPORT}))
        dissent_cohorts = tuple(sorted({v.cohort_id for v in values if v.stance == ClaimStance.DISSENT}))
        insufficient_cohorts = tuple(sorted({v.cohort_id for v in values if v.stance == ClaimStance.INSUFFICIENT}))
        abstain_cohorts = tuple(sorted({v.cohort_id for v in values if v.stance == ClaimStance.ABSTAIN}))
        support_vessels = tuple(sorted({v.vessel_id for v in values if v.stance == ClaimStance.SUPPORT}))
        dissent_vessels = tuple(sorted({v.vessel_id for v in values if v.stance == ClaimStance.DISSENT}))
        evidence_ids = tuple(sorted({ev for v in values for ev in v.evidence_ids}))
        assumptions = tuple(sorted({a for v in values for a in v.assumptions}))
        status = _claim_status(support_cohorts, dissent_cohorts, insufficient_cohorts, abstain_cohorts)
        claim = CouncilClaim(
            claim_id=claim_id, claim_text=values[0].claim_text, status=status,
            support_cohorts=support_cohorts, dissent_cohorts=dissent_cohorts,
            insufficient_cohorts=insufficient_cohorts, abstain_cohorts=abstain_cohorts,
            support_vessels=support_vessels, dissent_vessels=dissent_vessels,
            evidence_ids=evidence_ids, assumptions=assumptions,
            max_support_confidence=max((float(v.confidence) for v in values if v.stance == ClaimStance.SUPPORT), default=0.0),
            max_dissent_confidence=max((float(v.confidence) for v in values if v.stance == ClaimStance.DISSENT), default=0.0),
        )
        claims.append(claim)
        if support_cohorts and dissent_cohorts:
            disputes.append(CouncilDispute(claim_id, support_cohorts, dissent_cohorts))

    distinct_sources = len({
        (cohort.provider_id, cohort.model_id, cohort.configuration_id)
        for cohort in definition.cohorts
    })
    return CouncilAnalysis(
        council_digest=council_digest(definition),
        cohort_count=len(definition.cohorts),
        distinct_model_sources=distinct_sources,
        claims=tuple(claims), disputes=tuple(disputes), raw_observations=raw,
    )


def select_challenges(analysis: CouncilAnalysis) -> tuple[CouncilChallenge, ...]:
    challenges: list[CouncilChallenge] = []
    for claim in analysis.claims:
        reason: str | None = None
        if claim.status == ClaimStatus.DISPUTED:
            reason = "material_dispute"
        elif claim.status == ClaimStatus.MINORITY and max(
            claim.max_support_confidence, claim.max_dissent_confidence
        ) >= 0.90:
            reason = "high_confidence_minority"
        elif (
            claim.status == ClaimStatus.CONVERGED
            and claim.support_cohorts
            and not claim.dissent_cohorts
            and not claim.insufficient_cohorts
            and not claim.abstain_cohorts
            and not claim.evidence_ids
        ):
            reason = "unsupported_unanimity"
        if reason is not None:
            challenges.append(CouncilChallenge(
                claim_id=claim.claim_id, reason=reason,
                support_cohorts=claim.support_cohorts,
                dissent_cohorts=claim.dissent_cohorts,
                evidence_ids=claim.evidence_ids,
            ))
    return tuple(challenges)
