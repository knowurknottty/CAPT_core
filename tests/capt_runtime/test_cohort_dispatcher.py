import hashlib
import threading
import time

import pytest

from capt_runtime.cohort_dispatcher import (
    CohortDispatcher,
    cohort_prompt,
)
from capt_runtime.council import (
    CohortDefinition,
    CouncilDefinition,
    CouncilTier,
    CouncilValidationError,
    validate_council,
)


def custom_council(
    cohort_count: int = 20,
    vessels: int = 111,
) -> CouncilDefinition:
    cohorts = tuple(
        CohortDefinition(
            cohort_id=f"c{i + 1:02d}",
            provider_id=f"provider-{i + 1:02d}",
            model_id=f"model-{i + 1:02d}",
        )
        for i in range(cohort_count)
    )
    return CouncilDefinition(
        council_id="custom-parallel",
        tier=CouncilTier.CUSTOM,
        cohorts=cohorts,
        vessels_per_cohort=vessels,
    )


def completed(cohort, prompt, run_id, submitted_at):
    return {
        "driverRunId": run_id,
        "state": "completed",
        "observations": [{"summary": "ok:" + cohort.cohort_id}],
        "diagnostics": {
            "promptDigest": "sha256:"
            + hashlib.sha256(prompt.encode()).hexdigest(),
        },
    }


def test_custom_council_accepts_interactive_geometry():
    validate_council(custom_council(1, 1))
    validate_council(custom_council(20, 111))
    validate_council(custom_council(24, 1000))

    with pytest.raises(CouncilValidationError, match="CUSTOM_COHORT_COUNT_RANGE"):
        validate_council(custom_council(25, 11))
    with pytest.raises(CouncilValidationError, match="CUSTOM_VESSEL_COUNT_RANGE"):
        validate_council(custom_council(4, 1001))


def test_20_by_111_means_20_provider_calls_not_2220():
    active = 0
    peak = 0
    calls = []
    lock = threading.Lock()

    def slow(cohort, prompt, run_id, submitted_at):
        nonlocal active, peak
        with lock:
            calls.append(cohort.cohort_id)
            active += 1
            peak = max(peak, active)
        try:
            time.sleep(0.025)
            assert "logical_vessels: 111" in prompt
            assert "ONE provider inference" in prompt
            return completed(cohort, prompt, run_id, submitted_at)
        finally:
            with lock:
                active -= 1

    definition = custom_council(20, 111)
    result = CohortDispatcher(
        slow,
        max_concurrent_cohorts=6,
        slot_wait_timeout=2.0,
    ).dispatch(
        definition,
        objective="Find failure modes and converge a design.",
    )

    assert result.provider_call_count == 20
    assert result.logical_vessels == 2220
    assert len(calls) == 20
    assert len(set(calls)) == 20
    assert peak == 6
    assert result.governor_evidence["peakProviderCalls"] == 6
    assert result.as_evidence()["providerCallInvariant"] == "one_governed_execution_per_cohort"
    assert result.as_evidence()["physicalHttpCallsCountedSeparately"] is True
    assert all(
        record.vessels_per_cohort == 111
        for record in result.records
    )


def test_one_failed_cohort_does_not_cancel_independent_cohorts():
    seen = []

    def mixed(cohort, prompt, run_id, submitted_at):
        seen.append(cohort.cohort_id)
        if cohort.cohort_id == "c02":
            raise RuntimeError("synthetic provider failure")
        return completed(cohort, prompt, run_id, submitted_at)

    result = CohortDispatcher(
        mixed,
        max_concurrent_cohorts=4,
    ).dispatch(
        custom_council(4, 22),
        objective="Independent failure isolation.",
    )

    dispositions = {
        record.cohort.cohort_id: record.disposition
        for record in result.records
    }
    assert dispositions["c02"] == "failed"
    assert sum(value == "completed" for value in dispositions.values()) == 3
    assert result.provider_call_count == 4
    assert sorted(seen) == ["c01", "c02", "c03", "c04"]


def test_large_vessel_count_stays_prompt_compact_and_single_call():
    cohort = custom_council(1, 1000).cohorts[0]
    prompt = cohort_prompt("Analyze deeply.", cohort, 1000)

    assert "logical_vessels: 1000" in prompt
    assert "c01-v0001..c01-v1000" in prompt
    assert len(prompt) < 4000
