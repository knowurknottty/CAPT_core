"""Deterministic Council execution scheduler with capacity-bounded waves.

Maps a validated CouncilDefinition to an immutable CouncilExecutionSchedule
where each cohort is one physical inference job containing that cohort's N
vessel perspectives. Distinct cohorts remain distinct jobs even if provider,
model, and config match. Explicit provider capacity bounds how many cohort
jobs run concurrently; shortage produces deterministic waves/queue, never
cohort merging and never N-vessel fan-out.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

from .council import (
    CouncilDefinition,
    build_logical_blast,
    council_digest,
    validate_council,
)
from .contracts import digest


@dataclass(frozen=True)
class CohortExecutionSlot:
    """One bounded physical provider execution job for a cohort.

    Contains all logical vessels for this cohort as perspectives on one job.
    """
    slot_id: str
    cohort_id: str
    provider_id: str
    model_id: str
    configuration_id: str
    vessel_ids: tuple[str, ...]
    wave: int
    slot_in_wave: int


@dataclass(frozen=True)
class CouncilExecutionSchedule:
    """Immutable dispatch plan: one job per cohort, capacity-bounded waves."""
    schedule_id: str
    council_id: str
    council_digest: str
    schedule_digest: str
    logical_vessel_count: int
    physical_slot_count: int
    wave_count: int
    provider_capacity: tuple[tuple[str, int], ...]
    slots: tuple[CohortExecutionSlot, ...]


def schedule_council(
    definition: CouncilDefinition,
    provider_capacity: Optional[Mapping[str, int]] = None,
) -> CouncilExecutionSchedule:
    """Deterministically map a Council definition to capacity-bounded execution waves.

    provider_capacity maps provider_id -> max concurrent jobs. None means
    unlimited (one wave). Missing or zero capacity for a provider fails closed.

    Each cohort gets exactly one physical job regardless of shared provider/model/config.
    """
    validate_council(definition)

    logical_vessels = build_logical_blast(definition)
    logical_count = len(logical_vessels)

    # Group vessels by cohort for job construction.
    # Sort cohorts deterministically for reproducible scheduling.
    cohorts_sorted = sorted(
        definition.cohorts,
        key=lambda c: (c.provider_id, c.model_id, c.configuration_id, c.cohort_id),
    )

    # Build one job per cohort.
    jobs: list[dict] = []
    for cohort in cohorts_sorted:
        cohort_vessels = [
            v for v in logical_vessels
            if v.cohort_id == cohort.cohort_id
        ]
        vessel_ids = tuple(sorted(v.vessel_id for v in cohort_vessels))
        jobs.append({
            "cohort_id": cohort.cohort_id,
            "provider_id": cohort.provider_id,
            "model_id": cohort.model_id,
            "configuration_id": cohort.configuration_id,
            "vessel_ids": vessel_ids,
        })

    # Determine capacity bounds.
    capacity = {}
    capacity_specified = False
    if provider_capacity is not None:
        capacity_specified = True
        for k, v in provider_capacity.items():
            if isinstance(v, int) and v > 0:
                capacity[k] = v

    # Validate capacity for all providers used.
    providers_needed = {job["provider_id"] for job in jobs}
    if capacity_specified:
        for provider in providers_needed:
            if provider not in capacity:
                raise ValueError(
                    f"SCHEDULING_CAPACITY_MISSING: provider {provider} not in provider_capacity or capacity is zero"
                )

    # Schedule jobs into capacity-bounded waves.
    # Wave assignment: each provider tracks remaining capacity per wave.
    slots: list[CohortExecutionSlot] = []
    # Track active job count per provider in the current wave.
    wave_provider_load: dict[str, int] = {}
    wave = 1
    slot_in_wave = 0

    for job in jobs:
        provider = job["provider_id"]
        provider_cap = capacity.get(provider, float("inf"))

        # Check if provider has capacity in current wave.
        current_load = wave_provider_load.get(provider, 0)
        if current_load >= provider_cap:
            # Move to next wave.
            wave += 1
            wave_provider_load = {}
            slot_in_wave = 0

        # Assign job to this wave.
        slot_id = f"slot-{wave}-{slot_in_wave}-{job['cohort_id']}"
        slots.append(CohortExecutionSlot(
            slot_id=slot_id,
            cohort_id=job["cohort_id"],
            provider_id=job["provider_id"],
            model_id=job["model_id"],
            configuration_id=job["configuration_id"],
            vessel_ids=job["vessel_ids"],
            wave=wave,
            slot_in_wave=slot_in_wave,
        ))

        wave_provider_load[provider] = current_load + 1
        slot_in_wave += 1

    wave_count = max(s.wave for s in slots) if slots else 0

    # Compute schedule digest (distinct from council digest).
    schedule_id = f"schedule-{definition.council_id}"
    schedule_digest = digest({
        "type": "council_execution_schedule",
        "councilId": definition.council_id,
        "councilDigest": council_digest(definition),
        "waveCount": wave_count,
        "physicalSlotCount": len(slots),
        "logicalVesselCount": logical_count,
        "providerCapacity": [
            {"providerId": provider, "maxConcurrentJobs": value}
            for provider, value in sorted(capacity.items())
        ],
        "slots": [
            {
                "slotId": s.slot_id,
                "cohortId": s.cohort_id,
                "providerId": s.provider_id,
                "modelId": s.model_id,
                "wave": s.wave,
                "slotInWave": s.slot_in_wave,
                "vesselCount": len(s.vessel_ids),
            }
            for s in slots
        ],
    })

    return CouncilExecutionSchedule(
        schedule_id=schedule_id,
        council_id=definition.council_id,
        council_digest=council_digest(definition),
        schedule_digest=schedule_digest,
        logical_vessel_count=logical_count,
        physical_slot_count=len(slots),
        wave_count=wave_count,
        provider_capacity=tuple(sorted(capacity.items())),
        slots=tuple(slots),
    )


def council_schedule_to_record(schedule: CouncilExecutionSchedule) -> dict[str, object]:
    """Return the exact durable record for an admitted execution schedule."""
    return {
        "scheduleId": schedule.schedule_id,
        "councilId": schedule.council_id,
        "councilDigest": schedule.council_digest,
        "scheduleDigest": schedule.schedule_digest,
        "logicalVesselCount": schedule.logical_vessel_count,
        "physicalSlotCount": schedule.physical_slot_count,
        "waveCount": schedule.wave_count,
        "providerCapacity": [
            {"providerId": provider, "maxConcurrentJobs": value}
            for provider, value in schedule.provider_capacity
        ],
        "slots": [
            {
                "slotId": slot.slot_id,
                "cohortId": slot.cohort_id,
                "providerId": slot.provider_id,
                "modelId": slot.model_id,
                "configurationId": slot.configuration_id,
                "vesselIds": list(slot.vessel_ids),
                "wave": slot.wave,
                "slotInWave": slot.slot_in_wave,
            }
            for slot in schedule.slots
        ],
    }