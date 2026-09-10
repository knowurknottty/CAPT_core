from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from capt_runtime.council import (
    CohortDefinition,
    CouncilDefinition,
    CouncilLaunchAuthorization,
    CouncilTier,
    CouncilValidationError,
    build_logical_blast,
    council_digest,
    tier_preset,
    authorize_launch,
)


def make_council(tier: CouncilTier, *, vessels_per_cohort: int | None = None) -> CouncilDefinition:
    preset = tier_preset(tier, vessels_per_cohort=vessels_per_cohort)
    cohorts = tuple(
        CohortDefinition(
            cohort_id=f"c{i:02d}", provider_id=f"p{i % 4}", model_id=f"m{i:02d}"
        )
        for i in range(preset.cohort_count)
    )
    return CouncilDefinition(
        council_id=f"council-{tier.value}", tier=tier, cohorts=cohorts,
        vessels_per_cohort=preset.vessels_per_cohort,
    )
@pytest.mark.parametrize(
    ("tier", "cohorts", "vessels", "total"),
    [
        (CouncilTier.SMALL, 2, 3, 6),
        (CouncilTier.MEDIUM, 4, 6, 24),
        (CouncilTier.LARGE, 12, 9, 108),
        (CouncilTier.EXTREME, 24, 18, 432),
    ],
)
def test_owner_approved_tier_geometry(tier, cohorts, vessels, total):
    preset = tier_preset(tier)
    assert (preset.cohort_count, preset.vessels_per_cohort, preset.logical_vessels) == (
        cohorts, vessels, total,
    )

def test_extreme_accepts_1000_vessels_per_cohort_and_expands_24000():
    council = make_council(CouncilTier.EXTREME, vessels_per_cohort=1000)
    dispatches = build_logical_blast(council)
    assert len(dispatches) == 24_000
    assert dispatches[0].vessel_id == "c00-v0001"
    assert dispatches[-1].vessel_id == "c23-v1000"
    assert {item.cohort_id for item in dispatches} == {c.cohort_id for c in council.cohorts}


def test_every_vessel_inherits_provider_and_model_from_its_cohort():
    council = make_council(CouncilTier.MEDIUM)
    by_id = {cohort.cohort_id: cohort for cohort in council.cohorts}
    for item in build_logical_blast(council):
        parent = by_id[item.cohort_id]
        assert (item.provider_id, item.model_id) == (parent.provider_id, parent.model_id)

def test_council_digest_is_order_independent_but_model_sensitive():
    council = make_council(CouncilTier.SMALL)
    reordered = replace(council, cohorts=tuple(reversed(council.cohorts)))
    changed = replace(
        council,
        cohorts=(replace(council.cohorts[0], model_id="different-model"), council.cohorts[1]),
    )
    assert council_digest(reordered) == council_digest(council)
    assert council_digest(changed) != council_digest(council)


def test_extreme_requires_digest_bound_acknowledgement():
    council = make_council(CouncilTier.EXTREME)
    with pytest.raises(CouncilValidationError, match="EXTREME_ACK_REQUIRED"):
        authorize_launch(council, CouncilLaunchAuthorization(council_digest=""))
    digest = council_digest(council)
    authorize_launch(
        council,
        CouncilLaunchAuthorization(council_digest=digest, extreme_ack=True),
    )


def test_custom_extreme_scale_requires_separate_acknowledgement():
    council = make_council(CouncilTier.EXTREME, vessels_per_cohort=19)
    digest = council_digest(council)
    with pytest.raises(CouncilValidationError, match="CUSTOM_SCALE_ACK_REQUIRED"):
        authorize_launch(
            council,
            CouncilLaunchAuthorization(council_digest=digest, extreme_ack=True),
        )
    authorize_launch(
        council,
        CouncilLaunchAuthorization(
            council_digest=digest, extreme_ack=True, custom_scale_ack=True,
        ),
    )


def test_non_extreme_tier_does_not_require_extreme_ack():
    council = make_council(CouncilTier.LARGE)
    authorize_launch(
        council,
        CouncilLaunchAuthorization(council_digest=council_digest(council)),
    )


def test_rejects_tier_geometry_mutation_and_extreme_range_overflow():
    medium = make_council(CouncilTier.MEDIUM)
    with pytest.raises(CouncilValidationError, match="COHORT_COUNT_MISMATCH"):
        build_logical_blast(replace(medium, cohorts=medium.cohorts[:-1]))
    with pytest.raises(CouncilValidationError, match="EXTREME_VESSEL_COUNT_RANGE"):
        tier_preset(CouncilTier.EXTREME, vessels_per_cohort=1001)


from capt_runtime.council import VesselTiming


def test_vessel_timing_separates_logical_dispatch_from_transport_and_provider():
    timing = VesselTiming(logical_dispatched_at="2026-09-10T12:00:00Z")
    timing = timing.admit_transport("2026-09-10T12:00:01Z")
    timing = timing.start_provider("2026-09-10T12:00:02Z")
    timing = timing.complete("2026-09-10T12:00:03Z")
    assert timing.logical_dispatched_at < timing.transport_admitted_at
    assert timing.transport_admitted_at < timing.provider_started_at
    assert timing.provider_started_at < timing.completed_at


def test_vessel_timing_rejects_non_monotonic_transitions():
    timing = VesselTiming(logical_dispatched_at="2026-09-10T12:00:02Z")
    with pytest.raises(CouncilValidationError, match="TIMING_REGRESSION"):
        timing.admit_transport("2026-09-10T12:00:01Z")