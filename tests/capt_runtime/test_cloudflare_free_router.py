from __future__ import annotations

import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.backends.cloudflare_free_router import (
    CloudflareFreeEstimate,
    CloudflareFreeTierRouter,
    CloudflareSurface,
    CloudflareWorkClass,
)
from capt_runtime.tools.backends.cloudflare_free_tier import CloudflareUsageSnapshot


def test_router_selects_narrow_free_native_surface():
    router = CloudflareFreeTierRouter.default()
    assert router.route(CloudflareWorkClass.COORDINATION, CloudflareFreeEstimate()).surface is CloudflareSurface.WORKERS
    assert router.route(CloudflareWorkClass.DELEGATION, CloudflareFreeEstimate(queue_operations=2)).surface is CloudflareSurface.QUEUES
    assert router.route(CloudflareWorkClass.SHARED_STATE, CloudflareFreeEstimate(d1_rows_read=10)).surface is CloudflareSurface.D1
    assert router.route(CloudflareWorkClass.BROWSER, CloudflareFreeEstimate(browser_seconds=5)).surface is CloudflareSurface.BROWSER_RUN
    assert router.route(CloudflareWorkClass.INFERENCE, CloudflareFreeEstimate(ai_model="@cf/meta/llama-3.1-8b-instruct", ai_neurons=50)).surface is CloudflareSurface.WORKERS_AI


def test_router_never_falls_back_to_sandbox_or_containers():
    router = CloudflareFreeTierRouter.default()
    with pytest.raises(AuthorityViolation, match="CLOUDFLARE_FREE_NATIVE_SURFACE_UNAVAILABLE"):
        router.route(CloudflareWorkClass.ARBITRARY_COMPUTE, CloudflareFreeEstimate())


def test_router_enforces_usage_before_selection():
    router = CloudflareFreeTierRouter.default()
    usage = CloudflareUsageSnapshot(browser_seconds=540)
    with pytest.raises(AuthorityViolation, match="CLOUDFLARE_BROWSER_DAILY_BUDGET_EXHAUSTED"):
        router.route(
            CloudflareWorkClass.BROWSER,
            CloudflareFreeEstimate(browser_seconds=1),
            usage=usage,
        )


def test_router_rejects_paid_ai_model_and_ambiguous_estimate():
    router = CloudflareFreeTierRouter.default()
    with pytest.raises(AuthorityViolation, match="CLOUDFLARE_AI_MODEL_REQUIRES_PAID_AUTHORITY"):
        router.route(
            CloudflareWorkClass.INFERENCE,
            CloudflareFreeEstimate(ai_model="@cf/zai-org/glm-5.3-flash", ai_neurons=1),
        )
    with pytest.raises(ValueError, match="cloudflare_ai_model_required"):
        router.route(CloudflareWorkClass.INFERENCE, CloudflareFreeEstimate(ai_neurons=1))


def test_route_is_receipt_friendly_and_specific():
    route = CloudflareFreeTierRouter.default().route(
        CloudflareWorkClass.COORDINATION,
        CloudflareFreeEstimate(worker_requests=1, worker_cpu_ms=4),
    )
    assert route.reason == "free_native_workers_admitted"
    assert route.billing_authority == "free_only"
    assert route.provider_spend_ceiling_usd == 0
