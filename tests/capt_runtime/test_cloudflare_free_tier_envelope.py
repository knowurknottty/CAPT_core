from __future__ import annotations

import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.backends.cloudflare_free_tier import (
    CLOUDFLARE_FREE_TIER,
    CloudflareFreeTierEnvelope,
    CloudflareUsageSnapshot,
)


def test_verified_public_free_tier_limits_are_encoded():
    assert CLOUDFLARE_FREE_TIER.workers_requests_per_day == 100_000
    assert CLOUDFLARE_FREE_TIER.workers_cpu_ms_per_request == 10
    assert CLOUDFLARE_FREE_TIER.queue_operations_per_day == 10_000
    assert CLOUDFLARE_FREE_TIER.browser_seconds_per_day == 600
    assert CLOUDFLARE_FREE_TIER.workers_ai_neurons_per_day == 10_000
    assert CLOUDFLARE_FREE_TIER.d1_rows_read_per_day == 5_000_000
    assert CLOUDFLARE_FREE_TIER.d1_rows_written_per_day == 100_000


def test_internal_headroom_blocks_before_provider_ceiling():
    envelope = CloudflareFreeTierEnvelope.default()
    assert envelope.workers_requests_per_day < 100_000
    assert envelope.queue_operations_per_day < 10_000
    assert envelope.browser_seconds_per_day < 600
    assert envelope.workers_ai_neurons_per_day < 10_000
    assert envelope.d1_rows_read_per_day < 5_000_000
    assert envelope.d1_rows_written_per_day < 100_000


def test_admission_rejects_projected_worker_overrun():
    envelope = CloudflareFreeTierEnvelope.default()
    usage = CloudflareUsageSnapshot(workers_requests=envelope.workers_requests_per_day)
    with pytest.raises(AuthorityViolation, match="CLOUDFLARE_WORKERS_DAILY_BUDGET_EXHAUSTED"):
        envelope.require_workers(requests=1, cpu_ms=1, usage=usage)


def test_admission_rejects_paid_workers_ai_model_even_with_neurons_available():
    envelope = CloudflareFreeTierEnvelope.default()
    with pytest.raises(AuthorityViolation, match="CLOUDFLARE_AI_MODEL_REQUIRES_PAID_AUTHORITY"):
        envelope.require_workers_ai(model="@cf/zai-org/glm-5.3-flash", neurons=1)


def test_queue_browser_and_d1_budgets_are_independently_enforced():
    envelope = CloudflareFreeTierEnvelope.default()
    with pytest.raises(AuthorityViolation, match="CLOUDFLARE_QUEUE_DAILY_BUDGET_EXHAUSTED"):
        envelope.require_queue(operations=1, usage=CloudflareUsageSnapshot(queue_operations=envelope.queue_operations_per_day))
    with pytest.raises(AuthorityViolation, match="CLOUDFLARE_BROWSER_DAILY_BUDGET_EXHAUSTED"):
        envelope.require_browser(seconds=1, usage=CloudflareUsageSnapshot(browser_seconds=envelope.browser_seconds_per_day))
    with pytest.raises(AuthorityViolation, match="CLOUDFLARE_D1_READ_DAILY_BUDGET_EXHAUSTED"):
        envelope.require_d1(rows_read=1, rows_written=0, usage=CloudflareUsageSnapshot(d1_rows_read=envelope.d1_rows_read_per_day))
    with pytest.raises(AuthorityViolation, match="CLOUDFLARE_D1_WRITE_DAILY_BUDGET_EXHAUSTED"):
        envelope.require_d1(rows_read=0, rows_written=1, usage=CloudflareUsageSnapshot(d1_rows_written=envelope.d1_rows_written_per_day))
