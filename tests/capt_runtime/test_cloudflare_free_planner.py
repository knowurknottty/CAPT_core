from __future__ import annotations

from datetime import date, datetime, timezone

from capt_runtime.composition import create_runtime
from capt_runtime.tools.backends.cloudflare_free_router import (
    CloudflareFreeEstimate,
    CloudflareSurface,
    CloudflareWorkClass,
)


def test_runtime_owns_free_cloudflare_planner_and_usage_ledger(tmp_path):
    runtime = create_runtime(str(tmp_path / "runtime.db"))
    try:
        today = datetime.now(timezone.utc).date()
        plan = runtime.cloudflare_free_planner.reserve(
            operation_id="cf-plan-1",
            work_class=CloudflareWorkClass.DELEGATION,
            estimate=CloudflareFreeEstimate(queue_operations=2),
        )
        assert plan.route.surface is CloudflareSurface.QUEUES
        assert plan.reservation["state"] == "reserved"
        assert runtime.cloudflare_usage_ledger.snapshot(day=today).queue_operations == 2
    finally:
        runtime.close()


def test_planner_owns_quota_day_from_trusted_utc_clock(tmp_path):
    from datetime import date, datetime, timezone

    from capt_runtime.tools.backends.cloudflare_free_planner import (
        CloudflareFreeExecutionPlanner,
    )
    from capt_runtime.tools.backends.cloudflare_free_router import (
        CloudflareFreeTierRouter,
    )
    from capt_runtime.tools.backends.cloudflare_usage import CloudflareUsageLedger

    router = CloudflareFreeTierRouter.default()
    ledger = CloudflareUsageLedger(tmp_path / "trusted-day.sqlite", router=router)
    planner = CloudflareFreeExecutionPlanner(
        ledger,
        router,
        now=lambda: datetime(2026, 9, 8, 23, 59, tzinfo=timezone.utc),
    )
    planner.reserve(
        operation_id="trusted-day-op",
        work_class=CloudflareWorkClass.DELEGATION,
        estimate=CloudflareFreeEstimate(queue_operations=1),
    )
    assert ledger.snapshot(day=date(2026, 9, 8)).queue_operations == 1
    assert ledger.snapshot(day=date(2026, 9, 9)).queue_operations == 0


def test_planner_rejects_caller_selected_quota_day(tmp_path):
    import pytest

    from capt_runtime.errors import AuthorityViolation
    from capt_runtime.tools.backends.cloudflare_free_planner import (
        CloudflareFreeExecutionPlanner,
    )
    from capt_runtime.tools.backends.cloudflare_free_router import (
        CloudflareFreeTierRouter,
    )
    from capt_runtime.tools.backends.cloudflare_usage import CloudflareUsageLedger

    router = CloudflareFreeTierRouter.default()
    ledger = CloudflareUsageLedger(tmp_path / "forged-day.sqlite", router=router)
    planner = CloudflareFreeExecutionPlanner(
        ledger,
        router,
        now=lambda: datetime(2026, 9, 8, 23, 59, tzinfo=timezone.utc),
    )
    with pytest.raises(AuthorityViolation, match="CLOUDFLARE_QUOTA_DAY_UNTRUSTED"):
        planner.reserve(
            operation_id="forged-day-op",
            work_class=CloudflareWorkClass.DELEGATION,
            estimate=CloudflareFreeEstimate(queue_operations=1),
            day=date(2026, 9, 9),
        )
    assert ledger.snapshot(day=date(2026, 9, 9)).queue_operations == 0
