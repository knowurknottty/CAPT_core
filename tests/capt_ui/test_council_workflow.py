from __future__ import annotations

import json

import pytest

from capt_ui.operator.council_workflow import (
    CohortWorkflow,
    CouncilWorkflow,
    CouncilWorkflowError,
    bind_approval_results,
    council_launch_payload,
    donor_convergence_workflow,
)
from capt_ui.operator.runtime import Operator, OperatorError
from desktop.council_workflow import render_headless


def test_donor_template_exact_human_geometry(tmp_path):
    workflow = donor_convergence_workflow(str(tmp_path))
    assert len(workflow.cohorts) == 3
    assert workflow.logical_vessels == 33
    assert workflow.max_concurrent_cohorts == 1
    assert [c.vessels_per_cohort for c in workflow.cohorts] == [11, 11, 11]
    assert [(c.provider, c.model) for c in workflow.cohorts] == [
        ("openrouter", "qwen/qwen3.8-flash"),
        ("openrouter", "xiaomi/mimo-v2.6-flash"),
        ("openrouter", "z-ai/glm-5.3-flash"),
    ]


def test_approval_payloads_preserve_exact_authority_and_charter(tmp_path):
    workflow = donor_convergence_workflow(str(tmp_path))
    payloads = workflow.approval_payloads()
    assert len(payloads) == 3
    assert all(p["cohortSpec"]["vesselsPerCohort"] == 11 for p in payloads)
    assert all(
        p["cohortSpec"]["vesselCharterPolicy"]["schemaVersion"] == "2.0.0"
        for p in payloads
    )
    assert all(p["authorityProfile"]["filesystemRoot"] == str(tmp_path.resolve()) for p in payloads)
    assert all(p["authorityProfile"]["fileMutationAllowed"] for p in payloads)
    assert all(p["authorityProfile"]["shellAccessAllowed"] for p in payloads)
    assert all(p["authorityProfile"]["providerNetworkPolicy"] == "remote_allowed" for p in payloads)


def test_mixed_vessel_counts_are_rejected_before_runtime(tmp_path):
    workflow = CouncilWorkflow(
        council_id="council-mixed",
        mission_id="m-mixed",
        target_root=str(tmp_path),
        cohorts=(
            CohortWorkflow("a", "openrouter", "m1", "one", 11),
            CohortWorkflow("b", "openrouter", "m2", "two", 12),
        ),
    )
    with pytest.raises(CouncilWorkflowError, match="COUNCIL_VESSEL_COUNT_MISMATCH"):
        workflow.validate()


def test_bind_approval_results_cannot_cross_cohort_identity(tmp_path):
    workflow = donor_convergence_workflow(str(tmp_path))
    plans = []
    for payload in workflow.approval_payloads():
        plans.append({
            "requestId": "approval-" + payload["cohortSpec"]["cohortId"],
            "missionId": payload["missionId"],
            "taskId": payload["taskId"],
            "driverRunId": payload["driverRunId"],
            "cohortSpec": payload["cohortSpec"],
        })
    plans[1]["cohortSpec"] = {**plans[1]["cohortSpec"], "cohortId": "wrong"}
    with pytest.raises(CouncilWorkflowError, match="COUNCIL_APPROVAL_COHORT_MISMATCH"):
        bind_approval_results(workflow, plans)


def test_launch_payload_is_explicitly_sequential_for_donor_template(tmp_path):
    workflow = donor_convergence_workflow(str(tmp_path))
    plans = []
    for payload in workflow.approval_payloads():
        plans.append({
            "requestId": "approval-" + payload["cohortSpec"]["cohortId"],
            "missionId": payload["missionId"],
            "taskId": payload["taskId"],
            "driverRunId": payload["driverRunId"],
            "cohortSpec": payload["cohortSpec"],
        })
    executions = bind_approval_results(workflow, plans)
    launch = council_launch_payload(workflow, executions)
    assert launch["maxConcurrentCohorts"] == 1
    assert len(launch["executions"]) == 3
    assert sum(x["cohortSpec"]["vesselsPerCohort"] for x in launch["executions"]) == 33


class _FakeClient:
    def __init__(self):
        self.calls = []
        self.states = {}

    def capabilities(self):
        return {"commandOperations": ["run_approved_council_inspection"]}

    def command(self, op, payload, idempotency_key=None):
        self.calls.append((op, payload, idempotency_key))
        if op == "request_model_prompt_approval":
            cohort = payload["cohortSpec"]["cohortId"]
            request_id = "approval-" + cohort
            self.states[request_id] = {
                "state": "requested", "remainingUses": 1, "expiresAt": "2099-01-01T00:00:00Z"
            }
            return {
                "status": "accepted",
                "result": {
                    "requestId": request_id,
                    "missionId": payload["missionId"],
                    "taskId": payload["taskId"],
                    "driverRunId": payload["driverRunId"],
                    "cohortSpec": payload["cohortSpec"],
                },
            }
        if op == "submit_approval_decision":
            state = self.states[payload["requestId"]]
            state["state"] = "approved" if payload["decision"] == "approve" else "denied"
            return {"status": "accepted", "result": dict(state)}
        if op == "run_approved_council_inspection":
            return {
                "status": "accepted",
                "result": {
                    "councilId": payload["councilId"],
                    "cohortCount": len(payload["executions"]),
                    "maxConcurrentCohorts": payload["maxConcurrentCohorts"],
                },
            }
        raise AssertionError(op)

    def get_state(self, stream_id):
        request_id = stream_id.removeprefix("human_approval-")
        return {"requestId": request_id, **self.states[request_id]}


def _fake_operator() -> Operator:
    op = object.__new__(Operator)
    op._client = _FakeClient()
    op._connected = True
    op._identity = {}
    return op


def test_operator_workflow_never_auto_approves(tmp_path):
    op = _fake_operator()
    workflow = donor_convergence_workflow(str(tmp_path))
    session = op.request_council_workflow(workflow)
    assert [x["state"] for x in op.council_workflow_status(session)] == [
        "requested", "requested", "requested"
    ]
    assert not [call for call in op.client.calls if call[0] == "submit_approval_decision"]
    with pytest.raises(OperatorError, match="not all approved"):
        op.run_council_workflow(session)


def test_operator_explicit_human_decision_then_exact_launch(tmp_path):
    op = _fake_operator()
    workflow = donor_convergence_workflow(str(tmp_path))
    session = op.request_council_workflow(workflow)
    decisions = op.decide_council_workflow(session, "approve", "human clicked approve")
    assert len(decisions) == 3
    receipt = op.run_council_workflow(session)
    assert receipt["status"] == "accepted"
    launch_calls = [call for call in op.client.calls if call[0] == "run_approved_council_inspection"]
    assert len(launch_calls) == 1
    payload = launch_calls[0][1]
    assert payload["maxConcurrentCohorts"] == 1
    assert [x["cohortSpec"]["vesselsPerCohort"] for x in payload["executions"]] == [11, 11, 11]


def test_headless_surface_serializes_same_template(tmp_path):
    rendered = json.loads(render_headless(donor_convergence_workflow(str(tmp_path))))
    assert rendered["logicalVessels"] == 33
    assert rendered["maxConcurrentCohorts"] == 1
    assert [x["model"] for x in rendered["cohorts"]] == [
        "qwen/qwen3.8-flash",
        "xiaomi/mimo-v2.6-flash",
        "z-ai/glm-5.3-flash",
    ]
