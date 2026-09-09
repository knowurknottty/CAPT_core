"""Free-tier-native Cloudflare locality routing for CAPT."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from capt_runtime.errors import AuthorityViolation

from .cloudflare_ai_catalog import CloudflareAIModelCatalogSnapshot
from .cloudflare_free_tier import (
    CloudflareFreeTierEnvelope,
    CloudflareUsageSnapshot,
)


class CloudflareSurface(str, Enum):
    WORKERS = "workers"
    QUEUES = "queues"
    D1 = "d1"
    BROWSER_RUN = "browser_run"
    WORKERS_AI = "workers_ai"


class CloudflareWorkClass(str, Enum):
    COORDINATION = "coordination"
    DELEGATION = "delegation"
    SHARED_STATE = "shared_state"
    BROWSER = "browser"
    INFERENCE = "inference"
    ARBITRARY_COMPUTE = "arbitrary_compute"


@dataclass(frozen=True)
class CloudflareFreeEstimate:
    worker_requests: int = 0
    worker_cpu_ms: int = 0
    queue_operations: int = 0
    browser_seconds: int = 0
    ai_model: str | None = None
    ai_neurons: int = 0
    d1_rows_read: int = 0
    d1_rows_written: int = 0


@dataclass(frozen=True)
class CloudflareRouteDecision:
    surface: CloudflareSurface
    reason: str
    billing_authority: str = "free_only"
    provider_spend_ceiling_usd: int = 0


class CloudflareFreeTierRouter:
    def __init__(self, envelope: CloudflareFreeTierEnvelope) -> None:
        self.envelope = envelope

    @classmethod
    def default(cls) -> "CloudflareFreeTierRouter":
        return cls(CloudflareFreeTierEnvelope.default())

    def route(
        self,
        work_class: CloudflareWorkClass,
        estimate: CloudflareFreeEstimate,
        *,
        usage: CloudflareUsageSnapshot | None = None,
        ai_catalog: CloudflareAIModelCatalogSnapshot | None = None,
        at: datetime | None = None,
    ) -> CloudflareRouteDecision:
        usage = usage or CloudflareUsageSnapshot()
        if work_class is CloudflareWorkClass.COORDINATION:
            self.envelope.require_workers(
                requests=estimate.worker_requests,
                cpu_ms=estimate.worker_cpu_ms,
                usage=usage,
            )
            return CloudflareRouteDecision(
                CloudflareSurface.WORKERS, "free_native_workers_admitted"
            )
        if work_class is CloudflareWorkClass.DELEGATION:
            self.envelope.require_queue(
                operations=estimate.queue_operations, usage=usage
            )
            return CloudflareRouteDecision(
                CloudflareSurface.QUEUES, "free_native_queues_admitted"
            )
        if work_class is CloudflareWorkClass.SHARED_STATE:
            self.envelope.require_d1(
                rows_read=estimate.d1_rows_read,
                rows_written=estimate.d1_rows_written,
                usage=usage,
            )
            return CloudflareRouteDecision(
                CloudflareSurface.D1, "free_native_d1_admitted"
            )
        if work_class is CloudflareWorkClass.BROWSER:
            self.envelope.require_browser(
                seconds=estimate.browser_seconds, usage=usage
            )
            return CloudflareRouteDecision(
                CloudflareSurface.BROWSER_RUN, "free_native_browser_admitted"
            )
        if work_class is CloudflareWorkClass.INFERENCE:
            if not estimate.ai_model:
                raise ValueError("cloudflare_ai_model_required")
            self.envelope.require_workers_ai(
                model=estimate.ai_model,
                neurons=estimate.ai_neurons,
                usage=usage,
                catalog=ai_catalog,
                at=at,
            )
            return CloudflareRouteDecision(
                CloudflareSurface.WORKERS_AI, "free_native_workers_ai_admitted"
            )
        raise AuthorityViolation("CLOUDFLARE_FREE_NATIVE_SURFACE_UNAVAILABLE")
