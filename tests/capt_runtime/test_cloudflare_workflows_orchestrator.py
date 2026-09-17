from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from capt_runtime.tools.backends.cloudflare_free_planner import (
    CloudflareFreeExecutionPlanner,
)
from capt_runtime.tools.backends.cloudflare_free_router import (
    CloudflareFreeTierRouter,
)
from capt_runtime.tools.backends.cloudflare_native import (
    CloudflareDispatchNotStarted,
    CloudflareWorkflowIndeterminate,
    CloudflareWorkflowOrchestrator,
)
from capt_runtime.tools.backends.cloudflare_usage import CloudflareUsageLedger

DAY = date(2026, 9, 9)
INSTANCE_ID = "capt_" + "5" * 64


def planner(tmp_path):
    router = CloudflareFreeTierRouter.default()
    ledger = CloudflareUsageLedger(tmp_path / "usage.sqlite", router=router)
    return CloudflareFreeExecutionPlanner(ledger, router, now=lambda: datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)), ledger


class Bridge:
    def __init__(self):
        self.start_calls = 0
        self.status_calls: list[str] = []
        self.event_calls = 0
        self.start_error: Exception | None = None
        self.event_error: Exception | None = None

    def workflow_expected_instance_id(self, *, operation_id, workflow):
        return INSTANCE_ID

    def workflow_instance_start(self, *, operation_id, workflow, params):
        self.start_calls += 1
        if self.start_error is not None:
            raise self.start_error
        return {"instanceId": INSTANCE_ID, "status": "queued", "workflowId": "wf-1"}

    def workflow_instance_status(self, *, workflow, instance_id):
        self.status_calls.append(instance_id)
        return {"instanceId": instance_id, "workflowId": "wf-1", "status": "complete", "evidence": {"status": "complete"}}

    def workflow_instance_event(self, *, operation_id, workflow, instance_id, event_type, body):
        self.event_calls += 1
        if self.event_error is not None:
            raise self.event_error
        return {"instanceId": instance_id, "timestamp": "2026-09-09T14:00:00Z", "eventType": event_type}

    def workflow_instance_step_evidence(self, **kwargs):
        return {"kind": "json", "status": "complete", "error": None, "output": {"ok": True}, "eventType": None}


class NoBindingBridge(Bridge):
    def workflow_expected_instance_id(self, *, operation_id, workflow):
        raise CloudflareDispatchNotStarted("CLOUDFLARE_RESOURCE_BINDING_NOT_FOUND")


def test_start_commits_reserved_steps_only_after_provider_acknowledgement(tmp_path):
    p, ledger = planner(tmp_path)
    bridge = Bridge()
    orch = CloudflareWorkflowOrchestrator(p, bridge)
    result = orch.start(operation_id="wf-start-1", workflow="capt-mission", params={"missionId": "m-1"}, max_steps=25, day=DAY)
    assert result.instance_id == INSTANCE_ID
    assert result.provider_status == "queued"
    state = ledger.reserve("wf-start-1", "durable_orchestration", result.estimate, day=DAY)
    assert state["state"] == "committed"


def test_predispatch_binding_failure_creates_no_reservation(tmp_path):
    p, ledger = planner(tmp_path)
    orch = CloudflareWorkflowOrchestrator(p, NoBindingBridge())
    with pytest.raises(CloudflareDispatchNotStarted):
        orch.start(operation_id="wf-no-bind", workflow="capt-mission", params={}, max_steps=10, day=DAY)
    assert ledger.snapshot(day=DAY).workflow_steps == 0


def test_start_transport_ambiguity_keeps_reservation_locked_and_carries_instance_id(tmp_path):
    p, ledger = planner(tmp_path)
    bridge = Bridge()
    bridge.start_error = RuntimeError("lost response")
    orch = CloudflareWorkflowOrchestrator(p, bridge)
    with pytest.raises(CloudflareWorkflowIndeterminate) as exc:
        orch.start(operation_id="wf-lost", workflow="capt-mission", params={}, max_steps=50, day=DAY)
    assert exc.value.instance_id == INSTANCE_ID
    state = ledger.reserve("wf-lost", "durable_orchestration", exc.value.estimate, day=DAY)
    assert state["state"] == "reserved"


def test_reconcile_start_uses_same_instance_and_never_redispatches(tmp_path):
    p, ledger = planner(tmp_path)
    bridge = Bridge()
    bridge.start_error = RuntimeError("lost")
    orch = CloudflareWorkflowOrchestrator(p, bridge)
    with pytest.raises(CloudflareWorkflowIndeterminate):
        orch.start(operation_id="wf-recon", workflow="capt-mission", params={}, max_steps=75, day=DAY)
    bridge.start_error = None
    result = orch.reconcile_start(operation_id="wf-recon", workflow="capt-mission", max_steps=75, day=DAY)
    assert bridge.start_calls == 1
    assert bridge.status_calls == [INSTANCE_ID]
    assert result.provider_status == "complete"
    state = ledger.reserve("wf-recon", "durable_orchestration", result.estimate, day=DAY)
    assert state["state"] == "committed"


def test_event_ambiguity_is_not_retry_permission(tmp_path):
    p, _ = planner(tmp_path)
    bridge = Bridge()
    bridge.event_error = RuntimeError("lost")
    orch = CloudflareWorkflowOrchestrator(p, bridge)
    with pytest.raises(CloudflareWorkflowIndeterminate):
        orch.event(operation_id="evt-1", workflow="capt-mission", instance_id=INSTANCE_ID, event_type="approved", body={"ok": True})
    assert bridge.event_calls == 1


def test_provider_complete_is_observation_not_capt_completion(tmp_path):
    p, _ = planner(tmp_path)
    result = CloudflareWorkflowOrchestrator(p, Bridge()).status(workflow="capt-mission", instance_id=INSTANCE_ID)
    assert result.provider_status == "complete"
    assert result.effect == "workflow_provider_status_observed"
    assert not hasattr(result, "task_completed")
