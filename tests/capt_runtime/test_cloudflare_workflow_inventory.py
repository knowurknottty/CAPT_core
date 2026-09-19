from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from capt_runtime.tools.backends.cloudflare_native_api import (
    CloudflareNativeAPIBridge,
    CloudflareNativeAPIProfile,
)
from capt_runtime.tools.backends.cloudflare_resource_inventory import (
    CloudflareResourceKind,
    parse_cloudflare_resource_inventory,
)

NOW = datetime(2026, 9, 9, 13, 20, tzinfo=timezone.utc)


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
        self.calls.append((request, timeout))
        return FakeResponse(self.responses.pop(0))


def profile():
    return CloudflareNativeAPIProfile(
        account_id="acct-1",
        api_token_env="CF_API_TOKEN",
        worker_base_url="https://capt-control.example.workers.dev",
        worker_auth_env="CF_WORKER_TOKEN",
    )


def test_workflow_inventory_candidate_is_typed_unadopted_and_digest_bound():
    snapshot = parse_cloudflare_resource_inventory(
        account_id="acct-1",
        d1_rows=[],
        queue_rows=[],
        worker_rows=[],
        workflow_rows=[
            {
                "id": "182bd5e5-6e1a-4fe4-a799-aa6d9a6ab26e",
                "name": "capt-mission",
                "script_name": "capt-control",
            }
        ],
        fetched_at=NOW,
    )
    candidate = snapshot.require_exact(
        CloudflareResourceKind.WORKFLOW,
        "182bd5e5-6e1a-4fe4-a799-aa6d9a6ab26e",
        "capt-mission",
    )
    assert candidate.adopted is False
    assert candidate.adoption_authority == "human_required"
    assert snapshot.source_digest.startswith("sha256:")


def test_resource_inventory_fetches_complete_workflow_pages_read_only(monkeypatch):
    monkeypatch.setenv("CF_API_TOKEN", "api-secret")
    opener = Recorder(
        [
            {
                "success": True,
                "result": [],
                "result_info": {"page": 1, "total_pages": 1},
            },
            {"success": True, "result": []},
            {"success": True, "result": []},
            {
                "success": True,
                "result": [
                    {
                        "id": "wf-1",
                        "name": "capt-mission-a",
                        "script_name": "capt-control",
                    }
                ],
                "result_info": {"page": 1, "total_pages": 2},
            },
            {
                "success": True,
                "result": [
                    {
                        "id": "wf-2",
                        "name": "capt-mission-b",
                        "script_name": "capt-control",
                    }
                ],
                "result_info": {"page": 2, "total_pages": 2},
            },
        ]
    )
    bridge = CloudflareNativeAPIBridge(profile(), opener=opener, now=lambda: NOW)
    inventory = bridge.resource_inventory()
    assert {
        r.resource_id
        for r in inventory.resources
        if r.kind is CloudflareResourceKind.WORKFLOW
    } == {"wf-1", "wf-2"}
    assert all(request.get_method() == "GET" for request, _ in opener.calls)
    workflow_urls = [
        request.full_url
        for request, _ in opener.calls
        if "/accounts/acct-1/workflows?" in request.full_url
    ]
    assert len(workflow_urls) == 2
    assert "page=1" in workflow_urls[0]
    assert "page=2" in workflow_urls[1]
    assert not hasattr(bridge, "workflow_create")
    assert not hasattr(bridge, "workflow_delete")
    assert not hasattr(bridge, "workflow_update")


def test_resource_inventory_rejects_partial_workflow_pagination(monkeypatch):
    monkeypatch.setenv("CF_API_TOKEN", "api-secret")
    opener = Recorder(
        [
            {
                "success": True,
                "result": [],
                "result_info": {"page": 1, "total_pages": 1},
            },
            {"success": True, "result": []},
            {"success": True, "result": []},
            {
                "success": True,
                "result": [],
                "result_info": {"page": 1},
            },
        ]
    )
    bridge = CloudflareNativeAPIBridge(profile(), opener=opener, now=lambda: NOW)
    with pytest.raises(
        RuntimeError,
        match="cloudflare_workflow_inventory_pagination_unclassified",
    ):
        bridge.resource_inventory()
