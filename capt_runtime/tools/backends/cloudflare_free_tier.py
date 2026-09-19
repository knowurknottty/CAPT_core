"""Verified Cloudflare Free-plan ceilings and CAPT-side budget admission."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from capt_runtime.errors import AuthorityViolation

from .cloudflare_ai_catalog import CloudflareAIModelCatalogSnapshot


@dataclass(frozen=True)
class CloudflareFreeTierLimits:
    workers_requests_per_day: int = 100_000
    workers_cpu_ms_per_request: int = 10
    queue_operations_per_day: int = 10_000
    browser_seconds_per_day: int = 600
    workers_ai_neurons_per_day: int = 10_000
    d1_rows_read_per_day: int = 5_000_000
    d1_rows_written_per_day: int = 100_000
    workflow_steps_per_day: int = 3_000


CLOUDFLARE_FREE_TIER = CloudflareFreeTierLimits()


@dataclass(frozen=True)
class CloudflareUsageSnapshot:
    workers_requests: int = 0
    queue_operations: int = 0
    browser_seconds: int = 0
    workers_ai_neurons: int = 0
    d1_rows_read: int = 0
    d1_rows_written: int = 0
    workflow_steps: int = 0


@dataclass(frozen=True)
class CloudflareFreeTierEnvelope:
    workers_requests_per_day: int
    queue_operations_per_day: int
    browser_seconds_per_day: int
    workers_ai_neurons_per_day: int
    d1_rows_read_per_day: int
    d1_rows_written_per_day: int
    workflow_steps_per_day: int

    @classmethod
    def default(cls) -> "CloudflareFreeTierEnvelope":
        return cls(
            workers_requests_per_day=90_000,
            queue_operations_per_day=9_000,
            browser_seconds_per_day=540,
            workers_ai_neurons_per_day=9_000,
            d1_rows_read_per_day=4_500_000,
            d1_rows_written_per_day=90_000,
            workflow_steps_per_day=2_700,
        )

    @staticmethod
    def _nonnegative(value: int, code: str) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(code)

    def require_workers(
        self, *, requests: int, cpu_ms: int, usage: CloudflareUsageSnapshot | None = None
    ) -> None:
        usage = usage or CloudflareUsageSnapshot()
        self._nonnegative(requests, "workers_requests_invalid")
        self._nonnegative(cpu_ms, "workers_cpu_ms_invalid")
        if cpu_ms > CLOUDFLARE_FREE_TIER.workers_cpu_ms_per_request:
            raise AuthorityViolation("CLOUDFLARE_WORKERS_CPU_FREE_LIMIT_EXCEEDED")
        if usage.workers_requests + requests > self.workers_requests_per_day:
            raise AuthorityViolation("CLOUDFLARE_WORKERS_DAILY_BUDGET_EXHAUSTED")

    def require_workers_ai(
        self,
        *,
        model: str,
        neurons: int,
        usage: CloudflareUsageSnapshot | None = None,
        catalog: CloudflareAIModelCatalogSnapshot | None = None,
        at: datetime | None = None,
    ) -> None:
        usage = usage or CloudflareUsageSnapshot()
        self._nonnegative(neurons, "workers_ai_neurons_invalid")
        if catalog is None:
            raise AuthorityViolation("CLOUDFLARE_AI_MODEL_CATALOG_REQUIRED")
        if at is None:
            raise ValueError("cloudflare_ai_catalog_check_time_required")
        catalog.require_free(model, at=at)
        if usage.workers_ai_neurons + neurons > self.workers_ai_neurons_per_day:
            raise AuthorityViolation("CLOUDFLARE_AI_DAILY_BUDGET_EXHAUSTED")

    def require_queue(
        self, *, operations: int, usage: CloudflareUsageSnapshot | None = None
    ) -> None:
        usage = usage or CloudflareUsageSnapshot()
        self._nonnegative(operations, "queue_operations_invalid")
        if usage.queue_operations + operations > self.queue_operations_per_day:
            raise AuthorityViolation("CLOUDFLARE_QUEUE_DAILY_BUDGET_EXHAUSTED")

    def require_browser(
        self, *, seconds: int, usage: CloudflareUsageSnapshot | None = None
    ) -> None:
        usage = usage or CloudflareUsageSnapshot()
        self._nonnegative(seconds, "browser_seconds_invalid")
        if usage.browser_seconds + seconds > self.browser_seconds_per_day:
            raise AuthorityViolation("CLOUDFLARE_BROWSER_DAILY_BUDGET_EXHAUSTED")

    def require_workflow(
        self, *, steps: int, usage: CloudflareUsageSnapshot | None = None
    ) -> None:
        usage = usage or CloudflareUsageSnapshot()
        self._nonnegative(steps, "workflow_steps_invalid")
        if usage.workflow_steps + steps > self.workflow_steps_per_day:
            raise AuthorityViolation("CLOUDFLARE_WORKFLOW_DAILY_BUDGET_EXHAUSTED")

    def require_d1(
        self,
        *,
        rows_read: int,
        rows_written: int,
        usage: CloudflareUsageSnapshot | None = None,
    ) -> None:
        usage = usage or CloudflareUsageSnapshot()
        self._nonnegative(rows_read, "d1_rows_read_invalid")
        self._nonnegative(rows_written, "d1_rows_written_invalid")
        if usage.d1_rows_read + rows_read > self.d1_rows_read_per_day:
            raise AuthorityViolation("CLOUDFLARE_D1_READ_DAILY_BUDGET_EXHAUSTED")
        if usage.d1_rows_written + rows_written > self.d1_rows_written_per_day:
            raise AuthorityViolation("CLOUDFLARE_D1_WRITE_DAILY_BUDGET_EXHAUSTED")
