"""CAPT-UPG-016 shared Operator replay controls."""
from __future__ import annotations

from capt_ui.operator.runtime import Operator


class _ReplayClient:
    def __init__(self):
        self.queries = []
        self.commands = []

    def _query(self, payload):
        self.queries.append(payload)
        return {"result": {"echo": payload}}

    def command(self, op, payload, idempotency_key=None):
        self.commands.append((op, payload, idempotency_key))
        return {"status": "accepted", "op": op, "payload": payload}


def _operator():
    op = Operator.__new__(Operator)
    op._client = _ReplayClient()
    op._identity = {}
    op._connected = True
    return op


def test_operator_replay_state_at_uses_read_only_runtime_query():
    op = _operator()
    result = op.replay_state_at(12, stream_id="task-t-1")
    assert result["echo"] == {
        "op": "replay_state_at",
        "globalSequence": 12,
        "streamId": "task-t-1",
    }
    assert op.client.queries == [
        {"op": "replay_state_at", "globalSequence": 12, "streamId": "task-t-1"}
    ]
    assert op.client.commands == []


def test_operator_create_replay_fork_submits_governed_intent_command():
    op = _operator()
    payload = {
        "schemaVersion": "1.0.0",
        "forkId": "fork-ui-1",
        "sourceSequence": 12,
        "reason": "alternate governed continuation",
        "missionIntent": {
            "schemaVersion": "1.0.0",
            "missionId": "m-fork-ui-1",
            "objective": "Inspect an alternate historical path.",
            "rawRequest": "Inspect an alternate historical path.",
            "normalizedRequest": "inspect an alternate historical path",
            "scope": {},
            "constraints": [],
            "successCriteria": [],
            "terminationCriteria": [],
            "unresolvedAmbiguities": [],
            "budget": None,
            "requiresApproval": False,
            "requestedCapability": "",
            "resource": None,
            "operation": None,
            "riskClassification": "none",
            "policyReason": None,
            "taskId": None,
            "requestId": None,
        },
    }

    result = op.create_replay_fork(payload, idempotency_key="idem-ui-fork")

    assert result["status"] == "accepted"
    assert op.client.commands == [
        ("create_replay_fork", payload, "idem-ui-fork")
    ]
    assert op.client.queries == []
