"""CAPT-UPG-018 shared Operator Cohort Chamber projection/control."""
from __future__ import annotations

from capt_ui.operator.runtime import Operator


class _Client:
    def __init__(self):
        self.commands = []

    def get_state(self, stream_id):
        assert stream_id == "cohort-coh-1"
        return {
            "cohortId": "coh-1",
            "missionId": "m-1",
            "taskId": "t-1",
            "epoch": 1,
            "rounds": 0,
            "roundCap": 3,
            "participantCap": 2,
            "required": ["planner"],
            "roster": ["planner"],
            "participantCursors": {"planner": 7},
            "contributions": [
                {"contributionId": "c-1", "participant": "planner", "epoch": 1, "round": 0, "outcome": "PASS", "cursor": 7, "sourceSequences": [7], "material": False, "escalation": None}
            ],
            "stoppingReason": "SILENCE_QUORUM",
            "evidenceIds": ["ev-coh-1"],
            "latestSteer": None,
        }

    def command(self, op, payload, idempotency_key=None):
        self.commands.append((op, payload, idempotency_key))
        return {"status": "accepted", "classification": "accepted"}


def _operator():
    op = Operator.__new__(Operator)
    op._client = _Client()
    op._identity = {}
    op._connected = True
    return op


def test_operator_cohort_chamber_projects_authoritative_state_only():
    op = _operator()
    view = op.cohort_chamber("coh-1")
    assert view["authority"] == "projection_only"
    assert view["cohortId"] == "coh-1"
    assert view["projectedSilenceQuorum"] is True
    assert op.client.commands == []


def test_operator_chamber_steering_reuses_existing_governed_command():
    op = _operator()
    result = op.steer_deliberation("coh-1", "revisit evidence", reason="operator correction")
    assert result["status"] == "accepted"
    assert op.client.commands == [
        (
            "steer_deliberation",
            {"cohortId": "coh-1", "directive": "revisit evidence", "reason": "operator correction"},
            None,
        )
    ]
