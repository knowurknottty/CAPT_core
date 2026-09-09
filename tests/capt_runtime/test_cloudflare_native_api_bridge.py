from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.backends.cloudflare_native import CloudflareBrowserAction
from capt_runtime.tools.backends.cloudflare_native_api import (
    CloudflareNativeAPIBridge,
    CloudflareNativeAPIProfile,
    CloudflareProviderRejected,
)
from capt_runtime.tools.backends.cloudflare_resource_inventory import (
    CloudflareResourceKind,
)


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

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
        self.calls.append((request, timeout))
        return FakeResponse(self.responses.pop(0))


class BindingRegistry:
    def resolve(self, account_id, kind, alias):
        ids = {
            CloudflareResourceKind.QUEUE: "queue-123",
            CloudflareResourceKind.D1_DATABASE: "db-123",
            CloudflareResourceKind.WORKER_SCRIPT: "capt-control",
        }
        return {
            "accountId": account_id, "resourceKind": kind.value,
            "resourceId": ids[kind], "resourceName": alias,
            "targetAlias": alias,
            "targetEndpoint": ("https://capt-control.example.workers.dev" if kind is CloudflareResourceKind.WORKER_SCRIPT else None),
            "state": "active",
        }


def _binding_registry():
    return BindingRegistry()


def _profile():
    return CloudflareNativeAPIProfile(
        account_id="acct-1",
        api_token_env="CF_API_TOKEN",
        worker_base_url="https://capt-control.example.workers.dev",
        worker_auth_env="CF_WORKER_TOKEN",
        worker_alias="capt-control",
    )


def test_profile_rejects_unscoped_or_insecure_resources():
    with pytest.raises(AuthorityViolation, match="CLOUDFLARE_NATIVE_WORKER_REQUIRES_HTTPS"):
        CloudflareNativeAPIProfile(
            account_id="acct-1",
            api_token_env="CF_API_TOKEN",
            worker_base_url="http://example.com",
            worker_auth_env="CF_WORKER_TOKEN",
        )


def test_queue_push_uses_configured_resource_id_and_capt_effect_identity(monkeypatch):
    monkeypatch.setenv("CF_API_TOKEN", "api-secret")
    monkeypatch.setenv("CF_WORKER_TOKEN", "worker-secret")
    opener = Recorder([{"success": True, "result": {"metadata": {}}}])
    bridge = CloudflareNativeAPIBridge(_profile(), opener=opener, binding_registry=_binding_registry())
    result = bridge.queue_send(
        operation_id="queue-op-1",
        queue="capt-delegates",
        body={"delegateAssignmentId": "da-1"},
    )
    request = opener.calls[0][0]
    assert request.full_url.endswith("/accounts/acct-1/queues/queue-123/messages")
    assert request.headers["Authorization"] == "Bearer api-secret"
    assert result["messageId"] == "capt:queue-op-1"
    assert "api-secret" not in repr(result)


def test_d1_read_and_write_parse_metering(monkeypatch):
    monkeypatch.setenv("CF_API_TOKEN", "api-secret")
    monkeypatch.setenv("CF_WORKER_TOKEN", "worker-secret")
    opener = Recorder([
        {"success": True, "result": [{"success": True, "meta": {"rows_read": 3}, "results": [{"value": "ok"}]}]},
        {"success": True, "result": [{"success": True, "meta": {"rows_written": 1, "changes": 1}, "results": []}]},
    ])
    bridge = CloudflareNativeAPIBridge(_profile(), opener=opener, binding_registry=_binding_registry())
    read = bridge.d1_read(
        operation_id="d1-r-1", database="capt-state",
        statement="SELECT value FROM kv", params=[]
    )
    write = bridge.d1_write(
        operation_id="d1-w-1", database="capt-state",
        statement="UPDATE kv SET value=?", params=["v"]
    )
    assert read == {"rows": [{"value": "ok"}], "rowsRead": 3}
    assert write["rowsWritten"] == 1
    assert write["changeId"] == "capt:d1-w-1"
    assert all("/d1/database/db-123/query" in call[0].full_url for call in opener.calls)


def test_browser_and_workers_ai_use_closed_account_endpoints(monkeypatch):
    monkeypatch.setenv("CF_API_TOKEN", "api-secret")
    monkeypatch.setenv("CF_WORKER_TOKEN", "worker-secret")
    opener = Recorder([
        {"success": True, "result": "<html>ok</html>"},
        {"success": True, "result": {"response": "hello"}},
    ])
    bridge = CloudflareNativeAPIBridge(_profile(), opener=opener, binding_registry=_binding_registry())
    browser = bridge.browser_run(
        operation_id="browser-1",
        action=CloudflareBrowserAction.CONTENT,
        arguments={"url": "https://example.com"},
        estimated_seconds=4,
    )
    ai = bridge.workers_ai(
        operation_id="ai-1",
        model="@cf/meta/llama-3.1-8b-instruct",
        input_payload={"prompt": "hi"},
        estimated_neurons=20,
    )
    assert browser["artifactRef"].startswith("sha256:")
    assert opener.calls[0][0].full_url.endswith("/accounts/acct-1/browser-rendering/content")
    assert "/accounts/acct-1/ai/run/@cf/meta/llama-3.1-8b-instruct" in opener.calls[1][0].full_url
    assert ai["output"] == {"response": "hello"}


def test_worker_coordination_uses_separate_worker_secret(monkeypatch):
    monkeypatch.setenv("CF_API_TOKEN", "api-secret")
    monkeypatch.setenv("CF_WORKER_TOKEN", "worker-secret")
    opener = Recorder([{"ok": True}])
    bridge = CloudflareNativeAPIBridge(_profile(), opener=opener, binding_registry=_binding_registry())
    result = bridge.worker_request(
        operation_id="worker-1",
        route="/bot/coordinate",
        payload={"missionId": "m-1"},
        cpu_ms=4,
    )
    request = opener.calls[0][0]
    assert request.full_url == "https://capt-control.example.workers.dev/bot/coordinate"
    assert request.headers["Authorization"] == "Bearer worker-secret"
    assert result["status"] == 200


def test_provider_rejection_is_specific_and_does_not_leak_secret(monkeypatch):
    monkeypatch.setenv("CF_API_TOKEN", "api-secret")
    monkeypatch.setenv("CF_WORKER_TOKEN", "worker-secret")
    opener = Recorder([{"success": False, "errors": [{"code": 1001, "message": "denied"}]}])
    bridge = CloudflareNativeAPIBridge(_profile(), opener=opener, binding_registry=_binding_registry())
    with pytest.raises(CloudflareProviderRejected, match="cloudflare_api_rejected:1001") as caught:
        bridge.queue_send(operation_id="queue-denied", queue="capt-delegates", body={})
    assert "api-secret" not in str(caught.value)


def test_missing_secret_is_proven_pre_dispatch(monkeypatch):
    from capt_runtime.tools.backends.cloudflare_native import (
        CloudflareDispatchNotStarted,
    )

    monkeypatch.delenv("CF_API_TOKEN", raising=False)
    monkeypatch.delenv("CF_WORKER_TOKEN", raising=False)
    bridge = CloudflareNativeAPIBridge(_profile(), opener=Recorder([]), binding_registry=_binding_registry())
    with pytest.raises(CloudflareDispatchNotStarted, match="CLOUDFLARE_SECRET_UNAVAILABLE"):
        bridge.queue_send(
            operation_id="queue-no-secret",
            queue="capt-delegates",
            body={},
        )


def test_estimated_metering_is_labeled_reserved_ceiling(monkeypatch):
    monkeypatch.setenv("CF_API_TOKEN", "api-secret")
    monkeypatch.setenv("CF_WORKER_TOKEN", "worker-secret")
    opener = Recorder([
        {"success": True, "result": "<html>ok</html>"},
        {"success": True, "result": {"response": "hello"}},
    ])
    bridge = CloudflareNativeAPIBridge(_profile(), opener=opener, binding_registry=_binding_registry())
    browser = bridge.browser_run(
        operation_id="browser-meter",
        action=CloudflareBrowserAction.CONTENT,
        arguments={"url": "https://example.com"},
        estimated_seconds=4,
    )
    ai = bridge.workers_ai(
        operation_id="ai-meter",
        model="@cf/meta/llama-3.1-8b-instruct",
        input_payload={"prompt": "hi"},
        estimated_neurons=20,
    )
    assert browser["usageBasis"] == "reserved_ceiling"
    assert ai["usageBasis"] == "reserved_ceiling"


def test_browser_content_artifact_identity_binds_provider_result(monkeypatch):
    monkeypatch.setenv("CF_API_TOKEN", "api-secret")
    monkeypatch.setenv("CF_WORKER_TOKEN", "worker-secret")
    opener = Recorder([{"success": True, "result": "<html>bound</html>"}])
    bridge = CloudflareNativeAPIBridge(_profile(), opener=opener, binding_registry=_binding_registry())
    result = bridge.browser_run(
        operation_id="browser-bound",
        action=CloudflareBrowserAction.CONTENT,
        arguments={"url": "https://example.com"},
        estimated_seconds=3,
    )
    assert result["artifactRef"].startswith("sha256:")
    assert result["artifactRef"] != "capt:browser-bound"


def test_binary_browser_actions_require_local_spool_before_dispatch(monkeypatch):
    from capt_runtime.tools.backends.cloudflare_native import (
        CloudflareDispatchNotStarted,
    )

    monkeypatch.setenv("CF_API_TOKEN", "api-secret")
    monkeypatch.setenv("CF_WORKER_TOKEN", "worker-secret")
    opener = Recorder([])
    bridge = CloudflareNativeAPIBridge(_profile(), opener=opener, binding_registry=_binding_registry())
    for action in (CloudflareBrowserAction.PDF, CloudflareBrowserAction.SCREENSHOT):
        with pytest.raises(
            CloudflareDispatchNotStarted,
            match="CLOUDFLARE_BROWSER_BINARY_ARTIFACT_SPOOL_REQUIRED",
        ):
            bridge.browser_run(
                operation_id=f"browser-{action.value}",
                action=action,
                arguments={"url": "https://example.com"},
                estimated_seconds=3,
            )
    assert opener.calls == []


def test_binary_spool_requirement_precedes_secret_resolution(monkeypatch):
    from capt_runtime.tools.backends.cloudflare_native import (
        CloudflareDispatchNotStarted,
    )

    monkeypatch.delenv("CF_API_TOKEN", raising=False)
    opener = Recorder([])
    bridge = CloudflareNativeAPIBridge(
        _profile(), opener=opener, binding_registry=_binding_registry()
    )
    with pytest.raises(
        CloudflareDispatchNotStarted,
        match="CLOUDFLARE_BROWSER_BINARY_ARTIFACT_SPOOL_REQUIRED",
    ):
        bridge.browser_run(
            operation_id="browser-no-spool-no-secret",
            action=CloudflareBrowserAction.PDF,
            arguments={"url": "https://example.com"},
            estimated_seconds=2,
        )
    assert opener.calls == []


def test_ai_model_catalog_is_read_only_paginated_and_metadata_bound(monkeypatch):
    monkeypatch.setenv("CF_API_TOKEN", "api-secret")
    monkeypatch.setenv("CF_WORKER_TOKEN", "worker-secret")
    now = datetime(2026, 9, 9, 4, 30, tzinfo=timezone.utc)
    opener = Recorder([
        {
            "success": True,
            "result": [
                {"name": "@cf/meta/free", "properties": []},
                {"name": "@cf/zai-org/glm-5.3-flash", "properties": [
                    {"property_id": "require_workers_paid", "value": "true"}
                ]},
            ],
            "result_info": {"page": 1, "total_pages": 1},
        }
    ])
    bridge = CloudflareNativeAPIBridge(_profile(), opener=opener, now=lambda: now, binding_registry=_binding_registry())
    catalog = bridge.ai_model_catalog()
    request = opener.calls[0][0]
    assert request.get_method() == "GET"
    assert "/accounts/acct-1/ai/models/search?" in request.full_url
    assert "include_deprecated=false" in request.full_url
    assert "per_page=100" in request.full_url
    assert request.headers["Authorization"] == "Bearer api-secret"
    assert catalog.fetched_at == now
    assert catalog.catalog_models == frozenset({"@cf/meta/free", "@cf/zai-org/glm-5.3-flash"})
    assert catalog.paid_required_models == frozenset({"@cf/zai-org/glm-5.3-flash"})
    assert catalog.source_digest.startswith("sha256:")


def test_ai_model_catalog_rejects_partial_or_invalid_pagination(monkeypatch):
    monkeypatch.setenv("CF_API_TOKEN", "api-secret")
    monkeypatch.setenv("CF_WORKER_TOKEN", "worker-secret")
    opener = Recorder([{"success": True, "result": [], "result_info": {"page": 1}}])
    bridge = CloudflareNativeAPIBridge(_profile(), opener=opener, binding_registry=_binding_registry())
    with pytest.raises(RuntimeError, match="cloudflare_ai_catalog_pagination_unclassified"):
        bridge.ai_model_catalog()


def test_resource_inventory_uses_get_only_and_returns_unadopted_candidates(monkeypatch):
    monkeypatch.setenv("CF_API_TOKEN", "api-secret")
    monkeypatch.setenv("CF_WORKER_TOKEN", "worker-secret")
    now = datetime(2026, 9, 9, 5, 15, tzinfo=timezone.utc)
    opener = Recorder([
        {"success": True, "result": [{"uuid": "db-1", "name": "capt-state"}], "result_info": {"page": 1, "total_pages": 1}},
        {"success": True, "result": [{"queue_id": "q-1", "queue_name": "capt-delegates"}]},
        {"success": True, "result": [{"id": "capt-control"}]},
    ])
    bridge = CloudflareNativeAPIBridge(_profile(), opener=opener, now=lambda: now, binding_registry=_binding_registry())
    inventory = bridge.resource_inventory()
    assert inventory.fetched_at == now
    assert inventory.account_id == "acct-1"
    assert {r.resource_id for r in inventory.resources} == {"db-1", "q-1", "capt-control"}
    assert all(r.adopted is False and r.adoption_authority == "human_required" for r in inventory.resources)
    assert all(request.get_method() == "GET" for request, _ in opener.calls)
    urls = [request.full_url for request, _ in opener.calls]
    assert any("/accounts/acct-1/d1/database?" in url for url in urls)
    assert any(url.endswith("/accounts/acct-1/queues") for url in urls)
    assert any(url.endswith("/accounts/acct-1/workers/scripts") for url in urls)
    assert not hasattr(bridge, "adopt_resource")
    assert not hasattr(bridge, "create_resource")


def test_resource_inventory_rejects_partial_d1_pagination(monkeypatch):
    monkeypatch.setenv("CF_API_TOKEN", "api-secret")
    monkeypatch.setenv("CF_WORKER_TOKEN", "worker-secret")
    opener = Recorder([{"success": True, "result": [], "result_info": {"page": 1}}])
    bridge = CloudflareNativeAPIBridge(_profile(), opener=opener, binding_registry=_binding_registry())
    with pytest.raises(RuntimeError, match="cloudflare_d1_inventory_pagination_unclassified"):
        bridge.resource_inventory()
