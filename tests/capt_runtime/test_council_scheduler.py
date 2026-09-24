"""Tests for the deterministic Council execution scheduler."""
import pytest

from capt_runtime.council import (
    CohortDefinition,
    CouncilDefinition,
    CouncilTier,
    council_digest,
    validate_council,
)
from capt_runtime.council_scheduler import (
    CohortExecutionSlot,
    CouncilExecutionSchedule,
    schedule_council,
)


def make_small_council():
    """Create a valid small council (2 cohorts x 3 vessels each)."""
    cohorts = (
        CohortDefinition("cohort-a", "openai", "gpt-5", "default"),
        CohortDefinition("cohort-b", "google", "gemini-pro", "default"),
    )
    return CouncilDefinition(
        council_id="council-test-1",
        tier=CouncilTier.SMALL,
        cohorts=cohorts,
        vessels_per_cohort=3,
    )


def test_scheduler_maps_to_bounded_physical_slots():
    """Each cohort becomes one physical job regardless of shared config."""
    definition = make_small_council()
    schedule = schedule_council(definition)

    # 2 cohorts x 3 vessels = 6 logical vessels
    assert schedule.logical_vessel_count == 6
    # 2 cohorts = 2 physical jobs (even if they shared provider/model/config)
    assert schedule.physical_slot_count == 2
    # Physical jobs == number of cohorts
    assert schedule.physical_slot_count == len(definition.cohorts)


def test_scheduler_is_deterministic():
    """Same definition always produces the same schedule."""
    definition = make_small_council()
    schedule1 = schedule_council(definition)
    schedule2 = schedule_council(definition)

    assert schedule1.schedule_id == schedule2.schedule_id
    assert schedule1.schedule_digest == schedule2.schedule_digest
    assert schedule1.physical_slot_count == schedule2.physical_slot_count
    assert schedule1.wave_count == schedule2.wave_count
    for slot1, slot2 in zip(schedule1.slots, schedule2.slots):
        assert slot1.slot_id == slot2.slot_id
        assert slot1.wave == slot2.wave
        assert slot1.slot_in_wave == slot2.slot_in_wave
        assert slot1.vessel_ids == slot2.vessel_ids


def test_scheduler_slot_has_all_cohort_vessels():
    """Each physical job contains all logical vessels for that cohort."""
    definition = make_small_council()
    schedule = schedule_council(definition)

    # Find slot for cohort-a (gpt-5)
    gpt_slot = None
    for slot in schedule.slots:
        if slot.provider_id == "openai":
            gpt_slot = slot
            break
    assert gpt_slot is not None
    assert len(gpt_slot.vessel_ids) == 3  # all 3 vessels map to this job
    assert gpt_slot.vessel_ids[0].startswith("cohort-a-v")


def test_scheduler_same_target_distinct_cohorts_remain_separate():
    """Same provider/model/config but different cohorts = separate jobs."""
    cohorts = (
        CohortDefinition("cohort-a", "openai", "gpt-5", "default"),
        CohortDefinition("cohort-b", "openai", "gpt-5", "default"),
    )
    definition = CouncilDefinition(
        council_id="council-same-target",
        tier=CouncilTier.SMALL,
        cohorts=cohorts,
        vessels_per_cohort=3,
    )
    schedule = schedule_council(definition)

    # 2 separate jobs even though identical provider/model/config
    assert schedule.physical_slot_count == 2
    # Each job has 3 vessels
    for slot in schedule.slots:
        assert len(slot.vessel_ids) == 3
    # Different cohort_ids in each slot
    cohort_ids = [slot.cohort_id for slot in schedule.slots]
    assert "cohort-a" in cohort_ids
    assert "cohort-b" in cohort_ids


def test_scheduler_capacity_one_produces_waves():
    """Capacity=1 for same provider forces sequential waves, one job at a time."""
    cohorts = (
        CohortDefinition("cohort-a", "openai", "gpt-5", "default"),
        CohortDefinition("cohort-b", "openai", "gpt-5", "default"),
    )
    definition = CouncilDefinition(
        council_id="council-cap-1",
        tier=CouncilTier.SMALL,
        cohorts=cohorts,
        vessels_per_cohort=3,
    )
    schedule = schedule_council(
        definition,
        provider_capacity={"openai": 1},
    )

    # 2 jobs total
    assert schedule.physical_slot_count == 2
    # Each job is its own wave (capacity=1 for openai)
    assert schedule.wave_count == 2
    # First wave has 1 job
    wave1_slots = [s for s in schedule.slots if s.wave == 1]
    assert len(wave1_slots) == 1
    # Second wave has 1 job
    wave2_slots = [s for s in schedule.slots if s.wave == 2]
    assert len(wave2_slots) == 1


def test_scheduler_different_providers_concurrent_with_cap_one():
    """Different providers with capacity=1 each can run concurrently in wave 1."""
    definition = make_small_council()
    schedule = schedule_council(
        definition,
        provider_capacity={"openai": 1, "google": 1},
    )

    # 2 jobs total, different providers
    assert schedule.physical_slot_count == 2
    # Both fit in wave 1 (per-provider capacity)
    assert schedule.wave_count == 1
    for slot in schedule.slots:
        assert slot.wave == 1


def test_scheduler_sufficient_capacity_allows_concurrency():
    """Sufficient capacity runs all jobs in one wave."""
    definition = make_small_council()
    schedule = schedule_council(
        definition,
        provider_capacity={"openai": 2, "google": 2},
    )

    # 2 jobs total
    assert schedule.physical_slot_count == 2
    # Both fit in one wave
    assert schedule.wave_count == 1
    for slot in schedule.slots:
        assert slot.wave == 1


def test_scheduler_missing_capacity_fails_closed():
    """Missing provider capacity raises scheduling error."""
    definition = make_small_council()
    with pytest.raises(ValueError, match="SCHEDULING_CAPACITY_MISSING"):
        schedule_council(
            definition,
            provider_capacity={"openai": 2},  # google missing
        )


def test_scheduler_zero_capacity_fails_closed():
    """Zero provider capacity is treated as missing."""
    definition = make_small_council()
    with pytest.raises(ValueError, match="SCHEDULING_CAPACITY_MISSING"):
        schedule_council(
            definition,
            provider_capacity={"openai": 0, "google": 0},
        )


def test_scheduler_invalid_definition_raises():
    """Invalid council definitions raise before scheduling."""
    bad_definition = CouncilDefinition(
        council_id="council-bad",
        tier=CouncilTier.SMALL,
        cohorts=(CohortDefinition("only-one", "openai", "gpt-5", "default"),),
        vessels_per_cohort=3,
    )
    with pytest.raises(Exception):
        schedule_council(bad_definition)


def test_scheduler_schedule_digest_is_stable():
    """Schedule digest is stable across identical definitions."""
    definition = make_small_council()
    schedule1 = schedule_council(definition)
    schedule2 = schedule_council(definition)
    assert schedule1.schedule_digest == schedule2.schedule_digest


def test_scheduler_schedule_digest_distinct_from_council_digest():
    """Schedule digest is different from the council definition digest."""
    definition = make_small_council()
    schedule = schedule_council(definition)
    cd = council_digest(definition)
    assert schedule.schedule_digest != cd


def test_scheduler_deterministic_plan_with_capacity():
    """Capacity-bounded scheduling is deterministic."""
    definition = make_small_council()
    capacity = {"openai": 1, "google": 1}
    schedule1 = schedule_council(definition, provider_capacity=capacity)
    schedule2 = schedule_council(definition, provider_capacity=capacity)
    assert schedule1.schedule_digest == schedule2.schedule_digest
    assert schedule1.wave_count == schedule2.wave_count
    for s1, s2 in zip(schedule1.slots, schedule2.slots):
        assert s1.wave == s2.wave
        assert s1.slot_in_wave == s2.slot_in_wave