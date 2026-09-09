from __future__ import annotations

from datetime import date

import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.backends.cloudflare_free_router import CloudflareFreeEstimate
from capt_runtime.tools.backends.cloudflare_usage import CloudflareUsageLedger


def test_reservation_is_atomic_and_idempotent(tmp_path):
    ledger = CloudflareUsageLedger(tmp_path / "usage.sqlite")
    estimate = CloudflareFreeEstimate(worker_requests=10, worker_cpu_ms=2)
    first = ledger.reserve("op-1", "coordination", estimate, day=date(2026, 9, 8))
    second = ledger.reserve("op-1", "coordination", estimate, day=date(2026, 9, 8))
    assert second == first
    usage = ledger.snapshot(day=date(2026, 9, 8))
    assert usage.workers_requests == 10


def test_same_operation_id_with_different_cost_is_integrity_violation(tmp_path):
    ledger = CloudflareUsageLedger(tmp_path / "usage.sqlite")
    ledger.reserve("op-1", "coordination", CloudflareFreeEstimate(worker_requests=1), day=date(2026, 9, 8))
    with pytest.raises(AuthorityViolation, match="CLOUDFLARE_USAGE_RESERVATION_DIGEST_MISMATCH"):
        ledger.reserve("op-1", "coordination", CloudflareFreeEstimate(worker_requests=2), day=date(2026, 9, 8))


def test_budget_is_checked_against_durable_reserved_usage(tmp_path):
    ledger = CloudflareUsageLedger(tmp_path / "usage.sqlite")
    ledger.reserve(
        "op-near-limit",
        "browser",
        CloudflareFreeEstimate(browser_seconds=540),
        day=date(2026, 9, 8),
    )
    with pytest.raises(AuthorityViolation, match="CLOUDFLARE_BROWSER_DAILY_BUDGET_EXHAUSTED"):
        ledger.reserve(
            "op-over",
            "browser",
            CloudflareFreeEstimate(browser_seconds=1),
            day=date(2026, 9, 8),
        )


def test_release_restores_reserved_budget_before_effect(tmp_path):
    ledger = CloudflareUsageLedger(tmp_path / "usage.sqlite")
    estimate = CloudflareFreeEstimate(queue_operations=100)
    ledger.reserve("op-q", "delegation", estimate, day=date(2026, 9, 8))
    ledger.release("op-q", reason="dispatch_never_happened")
    assert ledger.snapshot(day=date(2026, 9, 8)).queue_operations == 0


def test_commit_keeps_consumed_usage_and_is_idempotent(tmp_path):
    ledger = CloudflareUsageLedger(tmp_path / "usage.sqlite")
    estimate = CloudflareFreeEstimate(d1_rows_written=5)
    ledger.reserve("op-d1", "shared_state", estimate, day=date(2026, 9, 8))
    ledger.commit("op-d1")
    ledger.commit("op-d1")
    assert ledger.snapshot(day=date(2026, 9, 8)).d1_rows_written == 5


def test_separate_connections_cannot_oversubscribe_same_daily_budget(tmp_path):
    import threading

    path = tmp_path / "usage-shared.sqlite"
    left = CloudflareUsageLedger(path)
    right = CloudflareUsageLedger(path)
    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def reserve(ledger, operation_id):
        barrier.wait()
        try:
            ledger.reserve(
                operation_id, "browser",
                CloudflareFreeEstimate(browser_seconds=540),
                day=date(2026, 9, 8),
            )
            outcomes.append("reserved")
        except AuthorityViolation as exc:
            outcomes.append(str(exc))

    threads = [
        threading.Thread(target=reserve, args=(left, "op-left")),
        threading.Thread(target=reserve, args=(right, "op-right")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert outcomes.count("reserved") == 1
    assert outcomes.count("CLOUDFLARE_BROWSER_DAILY_BUDGET_EXHAUSTED") == 1
