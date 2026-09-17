from __future__ import annotations

import json
import re

import pytest

from capt_runtime.tools.backends.cloudflare_artifacts import (
    CloudflareBinaryArtifactSpool,
)
from capt_runtime.tools.backends.cloudflare_native import CloudflareDispatchNotStarted
from capt_runtime.tools.backends.cloudflare_native_api import (
    CloudflareNativeAPIBridge,
    CloudflareNativeAPIProfile,
)
from capt_runtime.tools.backends.cloudflare_resource_inventory import (
    CloudflareResourceKind,
)
from capt_runtime.tools.backends.cloudflare_workflows import (
    workflow_instance_id,
)


class FakeResponse:
    def __init__(self, payload, *, content_type="application/json"):
        self.payload = payload
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, *args):
        if isinstance(self.payload, bytes):
            return self.payload
        return json.dumps(self.payload).encode("utf-8")


class Recorder:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, request, timeout):
        self.calls.append((request, timeout))
        return self.responses.pop(0)


class BindingRegistry:
    def resolve(self, account_id, kind, alias):
        assert kind is CloudflareResourceKind.WORKFLOW
        return {
            "accountId": account_id,
            "resourceKind": "workflow",
            "resourceId": "wf-1",
            "resourceName": "capt-mission",
            "targetAlias": alias,
            "targetEndpoint": None,
            "state": "active",
        }


def profile():
    return CloudflareNativeAPIProfile(
        account_id="acct-1", api_token_env="CF_API_TOKEN",
        worker_base_url="https://capt-control.example.workers.dev", worker_auth_env="CF_WORKER_TOKEN",
    )


def test_workflow_instance_id_is_deterministic_and_not_provider_reserved():
    left = workflow_instance_id("acct-1", "wf-1", "op-1")
    right = workflow_instance_id("acct-1", "wf-1", "op-1")
    assert left == right
    assert re.fullmatch(r"capt_[0-9a-f]{64}", left)
    assert not left.startswith("cf_")


def test_workflow_start_requires_adopted_binding_before_secret_or_network(monkeypatch):
    monkeypatch.delenv("CF_API_TOKEN", raising=False)
    bridge = CloudflareNativeAPIBridge(profile(), opener=lambda *args, **kwargs: (_ for _ in ()).__throw__(AssertionError("network started")))
    with pytest.raises(CloudflareDispatchNotStarted, match="CLOUDFLARE_RESOURCE_BINDING_REGISTRY_REQUIRED"):
        bridge.workflow_instance_start(operation_id="op-1", workflow="capt-mission", params={"id": 1})


def test_workflow_start_uses_bound_name_capt_id_and_json_encoded_params(monkeypatch):
    monkeypatch.setenv("CF_API_TOKEN", "secret")
    expected_id = workflow_instance_id("acct-1", "wf-1", "op-1")
    opener = Recorder([FakeResponse({"success": True, "result": {"id": expected_id, "status": "queued", "version_id": "v1", "workflow_id": "wf-1"}})])
    bridge = CloudflareNativeAPIBridge(profile(), opener=opener, binding_registry=BindingRegistry())
    result = bridge.workflow_instance_start(operation_id="op-1", workflow="capt-mission", params={"b": 2, "a": 1})
    request = opener.calls[0][0]
    body = json.loads(request.data.decode("utf-8"))
    assert request.get_method() == "POST"
    assert request.full_url.endswith("/accounts/acct-1/workflows/capt-mission/instances")
    assert body["instance_id"] == expected_id
    assert body["params"] == '{"a":1,"b":2}'
    assert result["instanceId"] == expected_id
    assert result["status"] == "queued"


def test_workflow_status_rejects_unknown_provider_status(monkeypatch):
    monkeypatch.setenv("CF_API_TOKEN", "secret")
    opener = Recorder([FakeResponse({"success": True, "result": {"id": "whatever", "status": "generic"}})])
    bridge = CloudflareNativeAPIBridge(profile(), opener=opener, binding_registry=BindingRegistry())
    with pytest.raises(RuntimeError, match="cloudflare_workflow_status_unclassified"):
        bridge.workflow_instance_status(workflow="capt-mission", instance_id="capt_" + "0" * 64)


def test_workflow_event_encloses_operation_id_and_requires_instance_id_match(monkeypatch):
    monkeypatch.setenv("CF_API_TOKEN", "secret")
    instance_id = "capt_" + "1" * 64
    opener = Recorder([FakeResponse({"success": True, "result": {"instanceId": instance_id, "timestamp": "2026-09-09T13:45:00Z"}})])
    bridge = CloudflareNativeAPIBridge(profile(), opener=opener, binding_registry=BindingRegistry())
    result = bridge.workflow_instance_event(operation_id="evt-1", workflow="capt-mission", instance_id=instance_id, event_type="approved", body={"ok": True})
    request = opener.calls[0][0]
    payload = json.loads(request.data.decode("utf-8"))
    assert payload == {"operationId": "evt-1", "payload": {"ok": True}}
    assert result["instanceId"] == instance_id


def test_workflow_step_evidence_requires_spool_before_secret(monkeypatch):
    monkeypatch.delenv("CF_API_TOKEN", raising=False)
    bridge = CloudflareNativeAPIBridge(profile(), binding_registry=BindingRegistry())
    with pytest.raises(CloudflareDispatchNotStarted, match="CLOUDFLARE_WORKFLOW_STEP_ARTIFACT_SPOOL_REQUIRED"):
        bridge.workflow_instance_step_evidence(operation_id="step-op", workflow="capt-mission", instance_id="capt_" + "2" * 64, step_name="fetch #1", step_type="step")


def test_workflow_step_evidence_returns_typed_json(monkeypatch, tmp_path):
    monkeypatch.setenv("CF_API_TOKEN", "secret")
    instance_id = "capt_" + "3" * 64
    opener = Recorder([FakeResponse({"success": True, "result": {"status": "complete", "error": None, "output": {"ok": True}}})])
    bridge = CloudflareNativeAPIBridge(profile(), opener=opener, binding_registry=BindingRegistry(), artifact_spool=CloudflareBinaryArtifactSpool(tmp_path / "spool"))
    result = bridge.workflow_instance_step_evidence(operation_id="step-json", workflow="capt-mission", instance_id=instance_id, step_name="fetch #1", step_type="step", attempt=2)
    request = opener.calls[0][0]
    assert request.get_method() == "GET"
    assert "name=fetch+%231" in request.full_url and "type=step" in request.full_url and "attempt=2" in request.full_url
    assert result == {"kind": "json", "status": "complete", "error": None, "output": {"ok": True}, "eventType": None}


def test_workflow_step_evidence_spools_octet_stream(monkeypatch, tmp_path):
    monkeypatch.setenv("CF_API_TOKEN", "secret")
    instance_id = "capt_" + "4" * 64
    spool = CloudflareBinaryArtifactSpool(tmp_path / "spool")
    opener = Recorder([FakeResponse(b"stream-output", content_type="application/octet-stream")])
    bridge = CloudflareNativeAPIBridge(profile(), opener=opener, binding_registry=BindingRegistry(), artifact_spool=spool)
    result = bridge.workflow_instance_step_evidence(operation_id="step-bin", workflow="capt-mission", instance_id=instance_id, step_name="stream #1", step_type="step")
    assert result["kind"] == "binary"
    assert result["artifactAction"] == "workflow_step_evidence"
    assert result["artifactRef"].startswith("cloudflare-artifact://")
    read = spool.read(operation_id="step-bin", ref=result["artifactRef"], offset=0, limit=64)
    import base64
    assert base64.b64decode(read["dataBase64"]) == b"stream-output"
