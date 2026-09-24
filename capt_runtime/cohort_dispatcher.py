"""Native cohort-level Model Council dispatcher.

One cohort == one provider inference.
Logical vessels are perspectives inside that single inference and NEVER multiply
provider calls. Independent cohorts may execute concurrently.

This module is the preferred council execution path for interactive CAPT surfaces.
The older VesselDispatcher remains available only for explicit per-vessel
experiments.
"""
from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, Optional, Tuple

from capt_runtime.cohort_contract import compile_cohort_objective
from capt_runtime.council import (
    CohortDefinition,
    CouncilDefinition,
    CouncilLaunchAuthorization,
    VesselTiming,
    authorize_launch,
    council_digest,
)
from capt_runtime.vessel_dispatcher import (
    DISPOSITION_COMPLETED,
    DISPOSITION_FAILED,
    DISPOSITION_INVALIDATED,
    DISPOSITION_PENDING,
    DISPOSITION_STARVED,
    DISPOSITION_TIMED_OUT,
    TERMINAL_DISPOSITIONS,
    DispatchGovernor,
    ProviderDispatchTimedOut,
    ProviderSlotStarved,
    utc_now,
)


def _vessel_manifest_digest(cohort: CohortDefinition, count: int) -> str:
    payload = {
        "cohortId": cohort.cohort_id,
        "count": count,
        "vesselIds": [
            f"{cohort.cohort_id}-v{ordinal:04d}"
            for ordinal in range(1, count + 1)
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def cohort_prompt(
    objective: str,
    cohort: CohortDefinition,
    vessels_per_cohort: int,
) -> str:
    return compile_cohort_objective(
        objective,
        provider=cohort.provider_id,
        model=cohort.model_id,
        cohort_spec={
            "cohortId": cohort.cohort_id,
            "vesselsPerCohort": vessels_per_cohort,
            "configurationId": cohort.configuration_id,
        },
    )



@dataclass
class CohortDispatchRecord:
    cohort: CohortDefinition
    vessels_per_cohort: int
    logical_dispatch_time: str
    council_digest: str
    timing: VesselTiming = field(init=False)
    disposition: str = DISPOSITION_PENDING
    dispatch_result: Optional[Dict[str, Any]] = None
    provider_observation: Optional[str] = None
    prompt_digest: Optional[str] = None
    failure_reason: Optional[str] = None

    def __post_init__(self) -> None:
        self.timing = VesselTiming(logical_dispatched_at=self.logical_dispatch_time)

    @property
    def vessel_manifest_digest(self) -> str:
        return _vessel_manifest_digest(self.cohort, self.vessels_per_cohort)

    def record_transport_admission(self, ts: str) -> None:
        self.timing = self.timing.admit_transport(ts)

    def record_provider_start(self, ts: str) -> None:
        self.timing = self.timing.start_provider(ts)
    def complete(self, ts: str, result: Dict[str, Any]) -> None:
        self.dispatch_result = result
        observations = result.get("observations") or []
        if observations and isinstance(observations[0], dict):
            self.provider_observation = observations[0].get("summary")
        diagnostics = result.get("diagnostics") or {}
        if isinstance(diagnostics, dict):
            self.prompt_digest = diagnostics.get("promptDigest")
        if self.timing.provider_started_at is not None:
            self.timing = self.timing.complete(ts)
        self.disposition = DISPOSITION_COMPLETED

    def terminate(self, disposition: str, ts: str, reason: str) -> None:
        if disposition not in TERMINAL_DISPOSITIONS - {DISPOSITION_COMPLETED}:
            raise ValueError(f"invalid terminal disposition: {disposition}")
        self.failure_reason = reason
        if (
            self.timing.provider_started_at is not None
            and self.timing.completed_at is None
        ):
            self.timing = self.timing.complete(ts)
        self.disposition = disposition

    def as_evidence(self) -> Dict[str, Any]:
        return {
            "cohortId": self.cohort.cohort_id,
            "providerId": self.cohort.provider_id,
            "modelId": self.cohort.model_id,
            "configurationId": self.cohort.configuration_id,
            "logicalVessels": self.vessels_per_cohort,
            "vesselManifestDigest": self.vessel_manifest_digest,
            "councilDigest": self.council_digest,
            "timing": {
                "logicalDispatchedAt": self.timing.logical_dispatched_at,
                "transportAdmittedAt": self.timing.transport_admitted_at,
                "providerStartedAt": self.timing.provider_started_at,
                "completedAt": self.timing.completed_at,
            },
            "terminalDisposition": self.disposition,
            "verificationState": "unverified",
            "promptDigest": self.prompt_digest,
            "providerObservation": self.provider_observation,
            "failureReason": self.failure_reason,
        }


CohortInvocation = Callable[
    [CohortDefinition, str, str, str],
    Dict[str, Any],
]


@dataclass(frozen=True)
class CohortCouncilDispatchResult:
    council_digest: str
    logical_vessels: int
    records: Tuple[CohortDispatchRecord, ...]
    governor_evidence: Dict[str, int]

    @property
    def provider_call_count(self) -> int:
        return int(self.governor_evidence.get("totalProviderCalls", 0))

    @property
    def disposition_counts(self) -> Dict[str, int]:
        counts = {name: 0 for name in sorted(TERMINAL_DISPOSITIONS)}
        for record in self.records:
            if record.disposition in counts:
                counts[record.disposition] += 1
        return counts

    def as_evidence(self) -> Dict[str, Any]:
        return {
            "councilDigest": self.council_digest,
            "cohortCount": len(self.records),
            "logicalVessels": self.logical_vessels,
            "providerCallCount": self.provider_call_count,
            "providerCallInvariant": "one_call_per_cohort",
            "dispositionCounts": self.disposition_counts,
            "governor": dict(self.governor_evidence),
            "cohorts": [record.as_evidence() for record in self.records],
        }


class CohortDispatcher:
    """Dispatch independent cohorts concurrently; one provider call per cohort."""

    def __init__(
        self,
        invoker: CohortInvocation,
        *,
        max_concurrent_cohorts: int,
        slot_wait_timeout: Optional[float] = 30.0,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        if slot_wait_timeout is not None and slot_wait_timeout < 0:
            raise ValueError("slot_wait_timeout must be >= 0 or None")
        self.invoker = invoker
        self.governor = DispatchGovernor(max_concurrent_cohorts)
        self.slot_wait_timeout = slot_wait_timeout
        self.clock = clock

    @staticmethod
    def _looks_like_timeout(exc: BaseException) -> bool:
        if isinstance(exc, (TimeoutError, ProviderDispatchTimedOut)):
            return True
        message = str(exc).lower()
        return (
            "timeout" in message
            or "timed out" in message
            or "wall-clock budget exhausted" in message
        )

    def dispatch(
        self,
        definition: CouncilDefinition,
        *,
        objective: str,
        authorization: Optional[CouncilLaunchAuthorization] = None,
        invalidated_cohort_ids: Iterable[str] = (),
    ) -> CohortCouncilDispatchResult:
        if not objective.strip():
            raise ValueError("objective is required")
        if authorization is None:
            authorization = CouncilLaunchAuthorization(
                council_digest=council_digest(definition)
            )
        preview = authorize_launch(definition, authorization)
        logical_ts = self.clock()
        records = [
            CohortDispatchRecord(
                cohort=cohort,
                vessels_per_cohort=definition.vessels_per_cohort,
                logical_dispatch_time=logical_ts,
                council_digest=preview.council_digest,
            )
            for cohort in definition.cohorts
        ]
        invalidated = set(invalidated_cohort_ids)
        known = {record.cohort.cohort_id for record in records}
        unknown = invalidated - known
        if unknown:
            raise ValueError(
                "unknown invalidated cohort ids: " + ", ".join(sorted(unknown))
            )
        def run_one(record: CohortDispatchRecord) -> CohortDispatchRecord:
            cohort = record.cohort
            if cohort.cohort_id in invalidated:
                record.terminate(
                    DISPOSITION_INVALIDATED,
                    self.clock(),
                    "invalidated before transport admission",
                )
                return record

            record.record_transport_admission(self.clock())
            try:
                with self.governor.provider_slot(self.slot_wait_timeout):
                    record.record_provider_start(self.clock())
                    prompt = cohort_prompt(
                        objective, cohort, definition.vessels_per_cohort
                    )
                    driver_run_id = (
                        f"dr-{definition.council_id}-{cohort.cohort_id}"
                        .replace("/", "-")
                        .replace(" ", "-")
                    )
                    result = self.invoker(
                        cohort,
                        prompt,
                        driver_run_id,
                        record.timing.provider_started_at or self.clock(),
                    )
                    if result.get("state") != "completed":
                        raise RuntimeError(
                            "provider returned non-completed state: "
                            + str(result.get("state"))
                        )
                    record.complete(self.clock(), result)
            except ProviderSlotStarved as exc:
                record.terminate(
                    DISPOSITION_STARVED, self.clock(), str(exc)
                )
            except BaseException as exc:
                disposition = (
                    DISPOSITION_TIMED_OUT
                    if self._looks_like_timeout(exc)
                    else DISPOSITION_FAILED
                )
                record.terminate(
                    disposition,
                    self.clock(),
                    f"{type(exc).__name__}: {exc}",
                )
            return record

        worker_count = min(
            len(records) or 1,
            max(1, self.governor.limit),
        )
        with ThreadPoolExecutor(
            max_workers=worker_count,
            thread_name_prefix="capt-cohort",
        ) as pool:
            futures = [pool.submit(run_one, record) for record in records]
            for future in as_completed(futures):
                future.result()

        for record in records:
            if record.disposition not in TERMINAL_DISPOSITIONS:
                raise AssertionError(
                    f"cohort {record.cohort.cohort_id} has no terminal disposition"
                )

        evidence = self.governor.evidence()
        if evidence["activeProviderCalls"] != 0:
            raise AssertionError("provider slots leaked after cohort dispatch")
        if evidence["peakProviderCalls"] > evidence["slotLimit"]:
            raise AssertionError(
                "measured provider concurrency exceeded the slot limit"
            )
        if evidence["totalProviderCalls"] > len(records):
            raise AssertionError(
                "COHORT_PROVIDER_CALL_MULTIPLICATION_DETECTED"
            )

        return CohortCouncilDispatchResult(
            council_digest=preview.council_digest,
            logical_vessels=definition.logical_vessel_count,
            records=tuple(records),
            governor_evidence=evidence,
        )
