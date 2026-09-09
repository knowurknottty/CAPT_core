from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from capt_runtime.tools.backends.cloudflare_free_planner import (
    CloudflareFreeExecutionPlanner,
)
from capt_runtime.tools.backends.cloudflare_free_router import CloudflareFreeTierRouter
from capt_runtime.tools.backends.cloudflare_native import (
    CloudflareDispatchNotStarted,
    CloudflareNativeIndeterminate,
    CloudflareQueueDelegator,
    CloudflareWorkersCoordinator,
)
from capt_runtime.tools.backends.cloudflare_usage import CloudflareUsageLedger


class Bridge:
    def __init__(self):
        self.worker_calls = []
        self.queue_calls = []

    def worker_request(self, **kwargs):
        self.worker_calls.append(kwargs)
        return {"status": 200, "body": {"ok": True}}

    def queue_send(self, **kwargs):
        self.queue_calls.append(kwargs)
        return {"messageId": "msg-1"}


def _planner(tmp_path):
    router = CloudflareFreeTierRouter.default()
    ledger = CloudflareUsageLedger(tmp_path / "usage.sqlite", router=router)
    return CloudflareFreeExecutionPlanner(
        ledger, router, now=lambda: datetime(2026, 9, 8, 12, tzinfo=timezone.utc)
    ), ledger


def test_workers_coordination_reserves_then_commits(tmp_path):
    planner, ledger = _planner(tmp_path)
    bridge = Bridge()
    backend = CloudflareWorkersCoordinator(planner, bridge)
    result = backend.coordinate(
        operation_id="worker-op-1",
        route="/bot/coordinate",
        payload={"missionId": "m-1"},
        cpu_ms=4,
        day=date(2026, 9, 8),
    )
    assert result.status_code == 200
    assert result.effect == "workers_request_completed"
    assert ledger.snapshot(day=date(2026, 9, 8)).workers_requests == 1
    assert bridge.worker_calls[0]["route"] == "/bot/coordinate"


def test_queue_delegation_reserves_then_commits(tmp_path):
    planner, ledger = _planner(tmp_path)
    bridge = Bridge()
    backend = CloudflareQueueDelegator(planner, bridge)
    result = backend.delegate(
        operation_id="queue-op-1",
        queue="capt-delegates",
        body={"delegateAssignmentId": "da-1"},
        day=date(2026, 9, 8),
    )
    assert result.message_id == "msg-1"
    assert result.effect == "queue_message_enqueued"
    assert ledger.snapshot(day=date(2026, 9, 8)).queue_operations == 1


def test_pre_dispatch_failure_releases_reservation(tmp_path):
    planner, ledger = _planner(tmp_path)

    class NotStarted(Bridge):
        def worker_request(self, **kwargs):
            raise CloudflareDispatchNotStarted("workers_transport_not_opened")

    backend = CloudflareWorkersCoordinator(planner, NotStarted())
    with pytest.raises(CloudflareDispatchNotStarted, match="workers_transport_not_opened"):
        backend.coordinate(
            operation_id="worker-release-1",
            route="/bot/coordinate",
            payload={},
            cpu_ms=2,
            day=date(2026, 9, 8),
        )
    assert ledger.snapshot(day=date(2026, 9, 8)).workers_requests == 0


def test_uncertain_dispatch_keeps_reservation_locked(tmp_path):
    planner, ledger = _planner(tmp_path)

    class Uncertain(Bridge):
        def queue_send(self, **kwargs):
            raise RuntimeError("socket closed after send")

    backend = CloudflareQueueDelegator(planner, Uncertain())
    with pytest.raises(CloudflareNativeIndeterminate, match="queue_dispatch_outcome_unclassified"):
        backend.delegate(
            operation_id="queue-uncertain-1",
            queue="capt-delegates",
            body={"delegateAssignmentId": "da-2"},
            day=date(2026, 9, 8),
        )
    assert ledger.snapshot(day=date(2026, 9, 8)).queue_operations == 1


def test_native_api_pre_dispatch_secret_failure_releases_queue_budget(tmp_path, monkeypatch):
    from capt_runtime.tools.backends.cloudflare_native_api import (
        CloudflareNativeAPIBridge,
        CloudflareNativeAPIProfile,
    )

    monkeypatch.delenv("CF_API_TOKEN", raising=False)
    monkeypatch.delenv("CF_WORKER_TOKEN", raising=False)
    planner, ledger = _planner(tmp_path)
    bridge = CloudflareNativeAPIBridge(
        CloudflareNativeAPIProfile(
            account_id="acct-1",
            api_token_env="CF_API_TOKEN",
            worker_base_url="https://capt-control.example.workers.dev",
            worker_auth_env="CF_WORKER_TOKEN",
        ),
        binding_registry=type("QueueBindingRegistry", (), {"resolve": lambda self, account_id, kind, alias: {"accountId": account_id, "resourceKind": kind.value, "resourceId": "queue-123", "resourceName": alias, "targetAlias": alias, "targetEndpoint": None, "state": "active"}})(),
    )
    backend = CloudflareQueueDelegator(planner, bridge)
    with pytest.raises(CloudflareDispatchNotStarted, match="CLOUDFLARE_SECRET_UNAVAILABLE"):
        backend.delegate(
            operation_id="queue-no-secret",
            queue="capt-delegates",
            body={},
            day=date(2026, 9, 8),
        )
    assert ledger.snapshot(day=date(2026, 9, 8)).queue_operations == 0
