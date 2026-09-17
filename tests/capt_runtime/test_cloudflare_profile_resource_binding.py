from __future__ import annotations

import json

import pytest

from capt_runtime.tools.backends.cloudflare_native import CloudflareDispatchNotStarted
from capt_runtime.tools.backends.cloudflare_native_api import (
    CloudflareNativeAPIBridge,
    CloudflareNativeAPIProfile,
)
from capt_runtime.tools.backends.cloudflare_resource_inventory import (
    CloudflareResourceKind,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class Recorder:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, request, timeout):
        self.calls.append(request)
        return FakeResponse(self.responses.pop(0))


class Registry:
    def __init__(self):
        self.calls = []

    def resolve(self, account_id, kind, alias):
        self.calls.append((account_id, kind, alias))
        ids = {
            CloudflareResourceKind.QUEUE: "queue-123",
            CloudflareResourceKind.D1_DATABASE: "db-123",
            CloudflareResourceKind.WORKER_SCRIPT: "capt-control",
        }
        return {
            "accountId": account_id,
            "resourceKind": kind.value,
            "resourceId": ids[kind],
            "resourceName": alias,
            "targetAlias": alias,
            "targetEndpoint": ("https://capt-control.example.workers.dev" if kind is CloudflareResourceKind.WORKER_SCRIPT else None),
            "state": "active",
        }


def profile():
    return CloudflareNativeAPIProfile(
        account_id="acct-1",
        api_token_env="CF_API_TOKEN",
        worker_base_url="https://capt-control.example.workers.dev",
        worker_auth_env="CF_WORKER_TOKEN",
        worker_alias="capt-control",
    )


def test_bridge_resolves_queue_d1_and_worker_from_adopted_bindings(monkeypatch):
    monkeypatch.setenv("CF_API_TOKEN", "api-secret")
    monkeypatch.setenv("CF_WORKER_TOKEN", "worker-secret")
    opener = Recorder([
        {"success": True, "result": {"metadata": {}}},
        {"success": True, "result": [{"success": True, "meta": {"rows_read": 1, "rows_written": 0}, "results": [{"value": "ok"}]}]},
       {"ok": True},
    ])
    registry = Registry()
    bridge = CloudflareNativeAPIBridge(profile(), opener=opener, binding_registry=registry)
    bridge.queue_send(operation_id="q-1", queue="capt-delegates", body={})
    bridge.d1_read(operation_id="d1-1", database="capt-state", statement="SELECT 1", params=[])
    bridge.worker_request(operation_id="w-1", route="/bot/coordinate", payload={}, cpu_ms=1)
    assert registry.calls == [
        ("acct-1", CloudflareResourceKind.QUEUE, "capt-delegates"),
        ("acct-1", CloudflareResourceKind.D1_DATABASE, "capt-state"),
        ("acct-1", CloudflareResourceKind.WORKER_SCRIPT, "capt-control"),
    ]
    assert "/queues/queue-123/messages" in opener.calls[0].full_url
    assert "/d1/database/db-123/query" in opener.calls[1].full_url


def test_missing_registry_fails_before_resource_dispatch(monkeypatch):
    monkeypatch.setenv("CF_API_TOKEN", "api-secret")
    bridge = CloudflareNativeAPIBridge(profile(), opener=Recorder([]))
    with pytest.raises(CloudflareDispatchNotStarted, match="CLOUDFLARE_RESOURCE_BINDING_REGISTRY_REQUIRED"):
        bridge.queue_send(operation_id="q-missing", queue="capt-delegates", body={})
