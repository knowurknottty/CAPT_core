"""P0.2 regression tests: council transport-loss reattachment.

After transport loss, a council session may be reattached only when every
consumed cohort approval was consumed by this exact council lineage
(``<run_key>:cohort:<cohortId>`` derived from the session's own workflow
digest). Reattachment replays the original durable idempotency identity
through the existing duplicate path: it never manufactures a fresh attempt,
and provider dispatch happens at most once no matter how often reattach is
retried.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from capt_ui.operator.council_workflow import (
    donor_convergence_workflow,
    workflow_digest,
)
from capt_ui.operator.runtime import Operator, OperatorError


class _FakeClient:
    """Simulates the runtime side, including idempotent command handling."""

    def __init__(self, states):
        self.states = states
        self.commands = []
        self.dispatches = 0
        self.seen_keys = set()

    def capabilities(self):
        return {"commandOperations": ["run_approved_council_inspection"]}

    def get_state(self, stream_id):
        return self.states[stream_id[len("human_approval-"):]]

    def command(self, op, payload, run_key=None):
        assert op == "run_approved_council_inspection"
        self.commands.append((op, dict(payload), run_key))
        # The runtime deduplicates on the idempotency key: the provider is
        # dispatched exactly once per key no matter how often it is replayed.
        if run_key not in self.seen_keys:
            self.seen_keys.add(run_key)
            self.dispatches += 1
            status = "accepted"
        else:
            status = "idempotent"
        return {"status": status, "result": {"councilId": payload["councilId"]}}


def _operator(states):
    op = Operator.__new__(Operator)
    op._client = _FakeClient(states)
    return op


def _session(tmp_path):
    workflow = donor_convergence_workflow(str(tmp_path))
    digest = workflow_digest(workflow)
    short = digest.split(":")[-1][:16]
    run_key = "council-workflow:%s:run" % short
    approvals = []
    executions = []
    for payload in workflow.approval_payloads():
        cohort = payload["cohortSpec"]["cohortId"]
        request_id = "approval-" + cohort
        approvals.append({
            "requestId": request_id,
            "cohortSpec": {"cohortId": cohort},
            "provider": payload["provider"],
            "model": payload["model"],
        })
        executions.append({**payload, "approvalRequestId": request_id})
    session = {
        "workflow": workflow.to_record(),
        "workflowDigest": digest,
        "approvals": approvals,
        "executions": executions,
    }
    return session, run_key


def _states(session, run_key, *, consumed=(), consumed_by=None):
    states = {}
    for approval in session["approvals"]:
        request_id = approval["requestId"]
        cohort = approval["cohortSpec"]["cohortId"]
        if cohort in consumed:
            states[request_id] = {
                "state": "consumed",
                "consumedBy": consumed_by or ("%s:cohort:%s" % (run_key, cohort)),
                "consumedAt": "2026-09-28T00:00:01Z",
                "commandIssuedAt": "2026-09-27T23:59:00Z",
                "driverRunId": "dr-" + cohort,
                "missionId": "m-" + cohort,
                "taskId": "t-" + cohort,
                "remainingUses": 0,
                "expiresAt": "2030-01-01T00:00:00Z",
            }
        else:
            states[request_id] = {
                "state": "approved",
                "remainingUses": 1,
                "expiresAt": "2030-01-01T00:00:00Z",
            }
    return states


def _cohorts(session):
    return [a["cohortSpec"]["cohortId"] for a in session["approvals"]]


def test_status_rows_carry_consumption_lineage(tmp_path: Path):
    session, run_key = _session(tmp_path)
    cohorts = _cohorts(session)
    op = _operator(_states(session, run_key, consumed=(cohorts[0],)))
    rows = op.council_workflow_status(session)
    assert len(rows) == 3
    first, second = rows[0], rows[1]
    assert first["cohortId"] == cohorts[0]
    assert first["state"] == "consumed"
    assert first["consumedBy"] == "%s:cohort:%s" % (run_key, cohorts[0])
    assert first["consumedAt"] == "2026-09-28T00:00:01Z"
    assert first["driverRunId"] == "dr-" + cohorts[0]
    assert second["state"] == "approved"
    assert second["consumedBy"] is None


def test_reattach_same_lineage_replays_durable_identity(tmp_path: Path):
    """A cohort consumed by this council's own admission reattaches: the exact
    original idempotency key is replayed, no fresh attempt is manufactured."""
    session, run_key = _session(tmp_path)
    cohorts = _cohorts(session)
    op = _operator(_states(session, run_key, consumed=(cohorts[0],)))
    receipt = op.reattach_council_workflow(session)
    assert receipt["status"] == "accepted"
    assert len(op._client.commands) == 1
    _op, payload, key = op._client.commands[0]
    assert key == run_key
    assert payload["councilId"] == session["workflow"]["councilId"]
    assert len(payload["executions"]) == 3


def test_reattach_without_flag_still_requires_approved(tmp_path: Path):
    """The non-reattach path is unchanged: consumed approvals block launch."""
    session, run_key = _session(tmp_path)
    cohorts = _cohorts(session)
    op = _operator(_states(session, run_key, consumed=(cohorts[0],)))
    with pytest.raises(OperatorError, match="not all approved"):
        op.run_council_workflow(session)
    assert op._client.commands == []


def test_reattach_wrong_council_lineage_fails_closed(tmp_path: Path):
    """consumedBy from a different council digest is not this council's."""
    session, run_key = _session(tmp_path)
    cohorts = _cohorts(session)
    op = _operator(_states(
        session, run_key, consumed=(cohorts[0],),
        consumed_by="council-workflow:deadbeef:run:cohort:%s" % cohorts[0],
    ))
    with pytest.raises(OperatorError, match="not all approved"):
        op.reattach_council_workflow(session)
    assert op._client.commands == []


def test_reattach_wrong_idempotency_fails_closed(tmp_path: Path):
    session, run_key = _session(tmp_path)
    cohorts = _cohorts(session)
    op = _operator(_states(
        session, run_key, consumed=(cohorts[0],),
        consumed_by="someone-elses-use-id",
    ))
    with pytest.raises(OperatorError, match="not all approved"):
        op.reattach_council_workflow(session)
    assert op._client.commands == []


def test_triple_reattach_dispatches_provider_exactly_once(tmp_path: Path):
    """Transport loss may be retried any number of times; the provider is
    dispatched exactly once because the durable idempotency identity never
    changes."""
    session, run_key = _session(tmp_path)
    cohorts = _cohorts(session)
    op = _operator(_states(session, run_key, consumed=tuple(cohorts)))
    receipts = [op.reattach_council_workflow(session) for _ in range(3)]
    assert [r["status"] for r in receipts] == ["accepted", "idempotent", "idempotent"]
    assert op._client.dispatches == 1
    keys = [c[2] for c in op._client.commands]
    assert keys == [run_key, run_key, run_key]


def test_completed_run_is_harvestable_on_reattach(tmp_path: Path):
    """A reattached completed run returns the runtime's result (harvestable);
    a running run is observable -- neither is redispatched."""

    class _HarvestClient(_FakeClient):
        def command(self, op, payload, run_key=None):
            receipt = super().command(op, payload, run_key)
            receipt["result"]["runs"] = [
                {"driverRunId": "dr-" + a["cohortSpec"]["cohortId"], "state": "completed"}
                for a in session["approvals"]
            ]
            return receipt

    session, run_key = _session(tmp_path)
    cohorts = _cohorts(session)
    op = _operator(_states(session, run_key, consumed=tuple(cohorts)))
    op._client = _HarvestClient(op._client.states)
    receipt = op.reattach_council_workflow(session)
    assert receipt["status"] == "accepted"
    assert all(r["state"] == "completed" for r in receipt["result"]["runs"])
    assert op._client.dispatches == 1
