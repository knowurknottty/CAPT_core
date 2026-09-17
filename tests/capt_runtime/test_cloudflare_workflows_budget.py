from __future__ import annotations

from datetime import date

import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.backends.cloudflare_free_router import (
    CloudflareFreeEstimate,
    CloudflareFreeTierRouter,
    CloudflareSurface,
    CloudflareWorkClass,
)
from capt_runtime.tools.backends.cloudflare_free_tier import (
    CloudflareFreeTierEnvelope,
    CloudflareUsageSnapshot,
)
from capt_runtime.tools.backends.cloudflare_usage import CloudflareUsageLedger

DAY = date(2026, 9, 9)


def test_workflow_internal_step_ceiling_has_ten_percent_headroom():
    envelope = CloudflareFreeTierEnvelope.default()
    envelope.require_workflow(steps=2_700, usage=CloudflareUsageSnapshot())
    with pytest.raises(
        AuthorityViolation,
        match="CLOUDFLARE_WORKFLOW_DAILY_BUDGET_EXHAUSTED",
    ):
        envelope.require_workflow(steps=2_701, usage=CloudflareUsageSnapshot())


def test_durable_orchestration_routes_only_to_workflows():
    router = CloudflareFreeTierRouter.default()
    decision = router.route(
        CloudflareWorkClass.DURABLE_ORCHESTRATION,
        CloudflareFreeEstimate(workflow_steps=25),
    )
    assert decision.surface is CloudflareSurface.WORKFLOWS
    assert decision.reason == "free_native_workflows_admitted"
    assert decision.billing_authority == "free_only"
    assert decision.provider_spend_ceiling_usd == 0


def test_arbitrary_compute_remains_unroutable():
    router = CloudflareFreeTierRouter.default()
    with pytest.raises(
        AuthorityViolation,
        match="CLOUDFLARE_FREE_NATIVE_SURFACE_UNAVAILABLE",
    ):
        router.route(
            CloudflareWorkClass.ARBITRARY_COMPUTE,
            CloudflareFreeEstimate(),
        )


def test_workflow_reservation_is_durable_and_release_restores_capacity(tmp_path):
    ledger = CloudflareUsageLedger(tmp_path / "usage.sqlite")
    estimate = CloudflareFreeEstimate(workflow_steps=2_700)
    ledger.reserve(
        "wf-max",
        CloudflareWorkClass.DURABLE_ORCHESTRATION.value,
        estimate,
        day=DAY,
    )
    assert ledger.snapshot(day=DAY).workflow_steps == 2_700
    with pytest.raises(
        AuthorityViolation,
        match="CLOUDFLARE_WORKFLOW_DAILY_BUDGET_EXHAUSTED",
    ):
        ledger.reserve(
            "wf-over",
            CloudflareWorkClass.DURABLE_ORCHESTRATION.value,
            CloudflareFreeEstimate(workflow_steps=1),
            day=DAY,
        )
    ledger.release("wf-max", reason="dispatch_never_started")
    assert ledger.snapshot(day=DAY).workflow_steps == 0


def test_separate_connections_cannot_double_spend_workflow_steps(tmp_path):
    import threading

    path = tmp_path / "workflow-shared.sqlite"
    left = CloudflareUsageLedger(path)
    right = CloudflareUsageLedger(path)
    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def reserve(ledger: CloudflareUsageLedger, operation_id: str) -> None:
        barrier.wait()
        try:
            ledger.reserve(
                operation_id,
                CloudflareWorkClass.DURABLE_ORCHESTRATION.value,
                CloudflareFreeEstimate(workflow_steps=2_700),
                day=DAY,
            )
            outcomes.append("reserved")
        except AuthorityViolation as exc:
            outcomes.append(str(exc))

    threads = [
        threading.Thread(target=reserve, args=(left, "wf-left")),
        threading.Thread(target=reserve, args=(right, "wf-right")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert outcomes.count("reserved") == 1
    assert outcomes.count("CLOUDFLARE_WORKFLOW_DAILY_BUDGET_EXHAUSTED") == 1
