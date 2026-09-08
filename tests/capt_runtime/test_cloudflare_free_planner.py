from __future__ import annotations

from datetime import date

from capt_runtime.composition import create_runtime
from capt_runtime.tools.backends.cloudflare_free_router import (
    CloudflareFreeEstimate,
    CloudflareSurface,
    CloudflareWorkClass,
)


def test_runtime_owns_free_cloudflare_planner_and_usage_ledger(tmp_path):
    runtime = create_runtime(str(tmp_path / "runtime.db"))
    try:
        plan = runtime.cloudflare_free_planner.reserve(
            operation_id="cf-plan-1",
            work_class=CloudflareWorkClass.DELEGATION,
            estimate=CloudflareFreeEstimate(queue_operations=2),
            day=date(2026, 9, 8),
        )
        assert plan.route.surface is CloudflareSurface.QUEUES
        assert plan.reservation["state"] == "reserved"
        assert runtime.cloudflare_usage_ledger.snapshot(day=date(2026, 9, 8)).queue_operations == 2
    finally:
        runtime.close()
