"""Governed Model Council vessel dispatcher.

This module turns the effect-free council topology in :mod:`capt_runtime.council`
into bounded provider execution without weakening CAPT's existing DriverHost trust
boundary.

Properties:
- the complete logical Vessel blast is materialized before provider execution;
- provider concurrency is enforced by a measured slot governor;
- each Vessel receives a distinct, provenance-bound perspective prompt;
- transport admission, provider start, and provider completion remain distinct;
- every admitted Vessel ends with an explicit terminal disposition;
- provider output remains untrusted observation data (never promoted to verified
  claims by this dispatcher);
- the production invocation path uses DriverHost + ProviderDriver with a scoped
  read-only capability lease.
"""
from __future__ import annotations

import hashlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Tuple

from capt_runtime.council import (
    CouncilDefinition,
    CouncilLaunchAuthorization,
    CouncilLaunchPreview,
    CouncilTier,
    CohortDefinition,
    VesselDispatchIntent,
    VesselTiming,
    authorize_launch,
    build_logical_blast,
    council_digest,
)
from capt_runtime.driver_host import DriverHost
from capt_runtime.driver_run import DriverRunAggregate
from capt_runtime.drivers.provider import (
    DESCRIPTOR as PROVIDER_DESCRIPTOR,
    ProviderDriver,
)
from capt_runtime.drivers.registry import DriverRegistry


DISPOSITION_PENDING = "pending"
DISPOSITION_COMPLETED = "completed"
DISPOSITION_FAILED = "failed"
DISPOSITION_STARVED = "starved"
DISPOSITION_INVALIDATED = "invalidated"
DISPOSITION_TIMED_OUT = "timed_out"
TERMINAL_DISPOSITIONS = frozenset(
    {
        DISPOSITION_COMPLETED,
        DISPOSITION_FAILED,
        DISPOSITION_STARVED,
        DISPOSITION_INVALIDATED,
        DISPOSITION_TIMED_OUT,
    }
)


class ProviderSlotStarved(RuntimeError):
    """No provider slot became available within the governed wait budget."""


class ProviderDispatchTimedOut(TimeoutError):
    """Provider execution exceeded its governed wall-clock budget."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def nearest_legal_geometry(requested: int = 44) -> Tuple[CouncilTier, int, int]:
    """Return the closest fixed legal council preset without silent substitution."""
    legal_counts = {
        6: (CouncilTier.SMALL, 2, 3),
        24: (CouncilTier.MEDIUM, 4, 6),
        108: (CouncilTier.LARGE, 12, 9),
    }
    nearest = min(legal_counts, key=lambda count: (abs(count - requested), count))
    return legal_counts[nearest]


def _build_fixed_council(
    *,
    council_id: str,
    tier: CouncilTier,
    cohort_count: int,
    vessels_per_cohort: int,
    provider_id: str = "hermes-local-stub",
    model_id: str = "qwen3.8-27b-local",
) -> CouncilDefinition:
    cohorts = tuple(
        CohortDefinition(
            cohort_id=f"c{i + 1:02d}",
            provider_id=provider_id,
            model_id=model_id,
            configuration_id="default",
        )
        for i in range(cohort_count)
    )
    return CouncilDefinition(
        council_id=council_id,
        tier=tier,
        cohorts=cohorts,
        vessels_per_cohort=vessels_per_cohort,
        synthesis_policy="weighted-evidence-union",
        challenge_policy="minority-dissent-recorded",
    )


def build_small_council(council_id: str = "r5-legal-small") -> CouncilDefinition:
    return _build_fixed_council(
        council_id=council_id,
        tier=CouncilTier.SMALL,
        cohort_count=2,
        vessels_per_cohort=3,
    )


def build_medium_council(council_id: str = "r5-legal-medium") -> CouncilDefinition:
    return _build_fixed_council(
        council_id=council_id,
        tier=CouncilTier.MEDIUM,
        cohort_count=4,
        vessels_per_cohort=6,
    )


def build_large_council(council_id: str = "r5-legal-large") -> CouncilDefinition:
    return _build_fixed_council(
        council_id=council_id,
        tier=CouncilTier.LARGE,
        cohort_count=12,
        vessels_per_cohort=9,
    )


def build_dispatcher_definition(
    council_id: str = "r5-legal-medium",
    tier_override: Optional[str] = None,
) -> CouncilDefinition:
    tier = (
        CouncilTier(tier_override)
        if tier_override is not None
        else nearest_legal_geometry(44)[0]
    )
    if tier is CouncilTier.SMALL:
        return build_small_council(council_id)
    if tier is CouncilTier.LARGE:
        return build_large_council(council_id)
    if tier is CouncilTier.MEDIUM:
        return build_medium_council(council_id)
    raise ValueError("EXTREME requires an explicit CouncilDefinition and authorization")


def validate_and_preview(
    definition: CouncilDefinition,
    authorization: Optional[CouncilLaunchAuthorization] = None,
) -> CouncilLaunchPreview:
    auth = authorization or CouncilLaunchAuthorization(
        council_digest=council_digest(definition),
        extreme_ack=definition.tier == CouncilTier.EXTREME,
        custom_scale_ack=False,
        maximum_spend_usd=None,
    )
    return authorize_launch(definition, auth)


def build_logical_blast_safe(
    definition: CouncilDefinition,
) -> Tuple[list[VesselDispatchIntent], CouncilLaunchPreview]:
    preview = validate_and_preview(definition)
    return list(build_logical_blast(definition)), preview


def nearest_legal_count(requested: int = 44) -> Tuple[int, CouncilTier, int, int]:
    tier, cohorts, vessels = nearest_legal_geometry(requested)
    return cohorts * vessels, tier, cohorts, vessels


def perspective_prompt(objective: str, vessel: VesselDispatchIntent) -> str:
    """Bind a unique independent perspective to one logical Vessel."""
    axis = (
        f"{vessel.cohort_id}/vessel-{vessel.ordinal:04d}/"
        f"{vessel.provider_id}/{vessel.model_id}/{vessel.configuration_id}"
    )
    return (
        f"{objective.strip()}\n\n"
        "CAPT Council independent-vessel instruction:\n"
        f"- vessel_id: {vessel.vessel_id}\n"
        f"- cohort_id: {vessel.cohort_id}\n"
        f"- perspective_axis: {axis}\n"
        "- reason independently; do not infer or imitate other Vessel outputs;\n"
        "- surface assumptions, uncertainty, counterevidence, and dissent;\n"
        "- return a bounded evidence-oriented observation, not an authoritative claim.\n"
    )


class DispatchGovernor:
    """Bounded provider-call slots with directly measured concurrency evidence."""

    def __init__(self, max_concurrent_provider_calls: int) -> None:
        if isinstance(max_concurrent_provider_calls, bool) or max_concurrent_provider_calls < 1:
            raise ValueError("max_concurrent_provider_calls must be >= 1")
        self.limit = int(max_concurrent_provider_calls)
        self._slots = threading.BoundedSemaphore(self.limit)
        self._lock = threading.Lock()
        self.active_provider_calls = 0
        self.peak_provider_calls = 0
        self.total_provider_calls = 0
        self.starved_slot_waits = 0

    @contextmanager
    def provider_slot(self, timeout: Optional[float] = None):
        acquired = self._slots.acquire(timeout=timeout)
        if not acquired:
            with self._lock:
                self.starved_slot_waits += 1
            raise ProviderSlotStarved("provider slot wait budget exhausted")
        with self._lock:
            self.active_provider_calls += 1
            self.total_provider_calls += 1
            self.peak_provider_calls = max(
                self.peak_provider_calls, self.active_provider_calls
            )
            if self.active_provider_calls > self.limit:
                raise AssertionError("provider concurrency governor exceeded its limit")
        try:
            yield
        finally:
            with self._lock:
                self.active_provider_calls -= 1
            self._slots.release()

    def evidence(self) -> Dict[str, int]:
        with self._lock:
            return {
                "slotLimit": self.limit,
                "activeProviderCalls": self.active_provider_calls,
                "peakProviderCalls": self.peak_provider_calls,
                "totalProviderCalls": self.total_provider_calls,
                "starvedSlotWaits": self.starved_slot_waits,
            }


@dataclass
class DispatchRecord:
    vessel: VesselDispatchIntent
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

    def record_transport_admission(self, ts: str) -> None:
        self.timing = self.timing.admit_transport(ts)

    def record_provider_start(self, ts: str) -> None:
        self.timing = self.timing.start_provider(ts)

    def _complete_timing_if_provider_started(self, ts: str) -> None:
        if self.timing.provider_started_at is not None and self.timing.completed_at is None:
            self.timing = self.timing.complete(ts)

    def complete(self, ts: str, result: Dict[str, Any]) -> None:
        self.dispatch_result = result
        observations = result.get("observations") or []
        if observations and isinstance(observations[0], dict):
            self.provider_observation = observations[0].get("summary")
        diagnostics = result.get("diagnostics") or {}
        if isinstance(diagnostics, dict):
            self.prompt_digest = diagnostics.get("promptDigest")
        self._complete_timing_if_provider_started(ts)
        self.disposition = DISPOSITION_COMPLETED

    def terminate(self, disposition: str, ts: str, reason: str) -> None:
        if disposition not in TERMINAL_DISPOSITIONS - {DISPOSITION_COMPLETED}:
            raise ValueError(f"invalid terminal disposition: {disposition}")
        self.failure_reason = reason
        self._complete_timing_if_provider_started(ts)
        self.disposition = disposition

    def as_evidence(self) -> Dict[str, Any]:
        return {
            "vesselId": self.vessel.vessel_id,
            "cohortId": self.vessel.cohort_id,
            "providerId": self.vessel.provider_id,
            "modelId": self.vessel.model_id,
            "configurationId": self.vessel.configuration_id,
            "ordinal": self.vessel.ordinal,
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


@dataclass(frozen=True)
class ProviderHostConfig:
    target_repo: str
    staging_root: str
    base_urls: Mapping[str, str]
    api_keys: Mapping[str, str] = field(default_factory=dict)
    max_seconds: int = 120
    max_tokens: int = 32_000


class ProviderHostInvoker:
    """Real DriverHost + ProviderDriver invocation for one Vessel at a time."""

    def __init__(self, config: ProviderHostConfig) -> None:
        self.config = config
        Path(config.target_repo).mkdir(parents=True, exist_ok=True)
        Path(config.staging_root).mkdir(parents=True, exist_ok=True)

    def _base_url(self, provider_id: str) -> str:
        value = self.config.base_urls.get(provider_id) or self.config.base_urls.get("*")
        if not value:
            raise KeyError(f"no provider endpoint configured for {provider_id}")
        return value

    def __call__(
        self,
        vessel: VesselDispatchIntent,
        prompt: str,
        driver_run_id: str,
        submitted_at: str,
    ) -> Dict[str, Any]:
        mission_id = f"council-{vessel.cohort_id}"
        task_id = f"vessel-{vessel.vessel_id}"
        vessel_stage = str(Path(self.config.staging_root) / vessel.vessel_id)
        Path(vessel_stage).mkdir(parents=True, exist_ok=True)

        registry = DriverRegistry()
        registry.register(PROVIDER_DESCRIPTOR)
        host = DriverHost(registry, vessel_stage, self.config.target_repo)
        driver = ProviderDriver(
            vessel_stage,
            provider_id=vessel.provider_id,
            model=vessel.model_id,
            base_url=self._base_url(vessel.provider_id),
            api_key=self.config.api_keys.get(vessel.provider_id, ""),
            dispatch_prompt=prompt,
        )
        host.select_driver(driver)

        operations = [
            "RepositoryRead",
            "FilesystemRead",
            "ArtifactCreate",
            "AnalysisOnly",
        ]
        lease = {
            "leaseId": f"lease-{driver_run_id}",
            "driverId": "provider",
            "missionId": mission_id,
            "taskId": task_id,
            "status": "active",
            "revoked": False,
            "operations": operations,
            "scope": {
                "kind": "filesystem",
                "rootPath": self.config.target_repo,
                "recursive": True,
                "allowedPaths": [self.config.target_repo, vessel_stage],
            },
            "budget": {"maxSeconds": self.config.max_seconds},
            "validFrom": "2000-01-01T00:00:00Z",
            "validUntil": "2100-01-01T00:00:00Z",
        }
        context = host.build_context(
            lease,
            permitted_tools=[],
            budgets={
                "maxSeconds": self.config.max_seconds,
                "maxTokens": self.config.max_tokens,
                "maxArtifacts": 1,
                "maxObservations": 1,
            },
            expected_artifacts=[
                {
                    "artifactPath": str(
                        Path(vessel_stage) / f"provider-analysis-{driver_run_id}.md"
                    ),
                    "artifactKind": "report",
                }
            ],
            termination={"onUnexpectedWrite": "fail"},
        )
        work_order = {
            "schemaVersion": "1.0.0",
            "driverRunId": driver_run_id,
            "driverId": "provider",
            "missionId": mission_id,
            "taskId": task_id,
            "workOrderVersion": 1,
            "contextSlice": context,
            "operations": operations,
        }
        run_state = DriverRunAggregate.create(work_order)
        return host.dispatch(
            work_order,
            context,
            run_state,
            now=submitted_at,
            lease=lease,
            budget={"maxSeconds": self.config.max_seconds},
        )


@dataclass(frozen=True)
class CouncilDispatchResult:
    council_digest: str
    requested_logical_vessels: int
    admitted_logical_vessels: int
    request_shortfall_starved: int
    records: Tuple[DispatchRecord, ...]
    governor_evidence: Dict[str, int]

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
            "requestedLogicalVessels": self.requested_logical_vessels,
            "admittedLogicalVessels": self.admitted_logical_vessels,
            "requestShortfallStarved": self.request_shortfall_starved,
            "dispositionCounts": self.disposition_counts,
            "governor": dict(self.governor_evidence),
            "vessels": [record.as_evidence() for record in self.records],
        }


Invocation = Callable[
    [VesselDispatchIntent, str, str, str],
    Dict[str, Any],
]


class VesselDispatcher:
    """Execute an authorized Council with bounded provider concurrency."""

    def __init__(
        self,
        invoker: Invocation,
        *,
        max_concurrent_provider_calls: int,
        slot_wait_timeout: Optional[float] = 30.0,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        if slot_wait_timeout is not None and slot_wait_timeout < 0:
            raise ValueError("slot_wait_timeout must be >= 0 or None")
        self.invoker = invoker
        self.governor = DispatchGovernor(max_concurrent_provider_calls)
        self.slot_wait_timeout = slot_wait_timeout
        self.clock = clock

    @staticmethod
    def _looks_like_timeout(exc: BaseException) -> bool:
        if isinstance(exc, (TimeoutError, ProviderDispatchTimedOut)):
            return True
        message = str(exc).lower()
        return "timeout" in message or "timed out" in message or "wall-clock budget exhausted" in message

    def dispatch(
        self,
        definition: CouncilDefinition,
        *,
        objective: str,
        authorization: Optional[CouncilLaunchAuthorization] = None,
        requested_logical_vessels: Optional[int] = None,
        invalidated_vessel_ids: Iterable[str] = (),
    ) -> CouncilDispatchResult:
        if not objective.strip():
            raise ValueError("objective is required")
        preview = validate_and_preview(definition, authorization)
        intents = tuple(build_logical_blast(definition))
        # Materialize every logical record before any external boundary crossing.
        logical_ts = self.clock()
        records = [
            DispatchRecord(intent, logical_ts, preview.council_digest)
            for intent in intents
        ]
        invalidated = set(invalidated_vessel_ids)
        known_ids = {record.vessel.vessel_id for record in records}
        unknown_invalidations = invalidated - known_ids
        if unknown_invalidations:
            raise ValueError(
                "unknown invalidated vessel ids: " + ", ".join(sorted(unknown_invalidations))
            )

        def run_one(record: DispatchRecord) -> DispatchRecord:
            vessel = record.vessel
            if vessel.vessel_id in invalidated:
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
                    prompt = perspective_prompt(objective, vessel)
                    driver_run_id = (
                        f"dr-{definition.council_id}-{vessel.vessel_id}"
                        .replace("/", "-")
                        .replace(" ", "-")
                    )
                    result = self.invoker(
                        vessel, prompt, driver_run_id, record.timing.provider_started_at or self.clock()
                    )
                    if result.get("state") != "completed":
                        raise RuntimeError(
                            f"provider returned non-completed state: {result.get('state')}"
                        )
                    record.complete(self.clock(), result)
            except ProviderSlotStarved as exc:
                record.terminate(DISPOSITION_STARVED, self.clock(), str(exc))
            except BaseException as exc:  # preserve disposition without hiding provider failures
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

        # More worker threads than provider slots make the semaphore the measured
        # authority for provider concurrency rather than executor width.
        worker_count = min(
            len(records) or 1,
            max(self.governor.limit * 4, self.governor.limit),
        )
        with ThreadPoolExecutor(
            max_workers=worker_count,
            thread_name_prefix="capt-vessel",
        ) as pool:
            futures = [pool.submit(run_one, record) for record in records]
            for future in as_completed(futures):
                future.result()

        for record in records:
            if record.disposition not in TERMINAL_DISPOSITIONS:
                raise AssertionError(
                    f"vessel {record.vessel.vessel_id} has no terminal disposition"
                )
        evidence = self.governor.evidence()
        if evidence["activeProviderCalls"] != 0:
            raise AssertionError("provider slots leaked after council dispatch")
        if evidence["peakProviderCalls"] > evidence["slotLimit"]:
            raise AssertionError("measured provider concurrency exceeded the slot limit")

        requested = (
            len(records)
            if requested_logical_vessels is None
            else int(requested_logical_vessels)
        )
        shortfall = max(0, requested - len(records))
        return CouncilDispatchResult(
            council_digest=preview.council_digest,
            requested_logical_vessels=requested,
            admitted_logical_vessels=len(records),
            request_shortfall_starved=shortfall,
            records=tuple(records),
            governor_evidence=evidence,
        )
