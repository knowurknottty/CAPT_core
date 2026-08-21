"""CAPT-UPG-016 operator-surface tests for historical replay/fork."""
from __future__ import annotations

from capt_runtime.scenario import TASK_ID, build_scenario
from capt_runtime.store import EventStore
from desktop.capt_runtime_service import RuntimeQueryService


def test_replay_state_at_query_returns_exact_historical_stream_without_mutation(tmp_path):
    db = str(tmp_path / "query.db")
    build_scenario(db)
    store = EventStore(db)
    manifest = store.load_checkpoint("cp-m0a-001")
    position = manifest["ledgerPosition"]["globalSequence"]
    before_head = store.head_sequence()
    current = store.require_state("task-" + TASK_ID)

    response = RuntimeQueryService(store).handle(
        {
            "op": "replay_state_at",
            "globalSequence": position,
            "streamId": "task-" + TASK_ID,
        }
    )

    assert response["ok"] is True
    result = response["result"]
    assert result["globalSequence"] == position
    assert result["headSequence"] == before_head
    assert result["streamId"] == "task-" + TASK_ID
    assert result["streamVersion"] == 4
    assert result["state"]["state"] == "running"
    assert result["stateDigest"].startswith("sha256:")
    assert store.head_sequence() == before_head
    assert store.require_state("task-" + TASK_ID) == current
    store.close()


def test_authenticated_replay_fork_command_builds_new_draft_mission_in_runtime(tmp_path):
    from capt_runtime.composition import create_runtime

    db = str(tmp_path / "command.db")
    build_scenario(db)
    comp = create_runtime(db)
    source_sequence = comp.store.load_checkpoint("cp-m0a-001")["ledgerPosition"]["globalSequence"]
    relay = comp.command_service("captain", "session-upg016")
    command = {
        "commandId": "cmd-fork-operator-001",
        "operatorId": "captain",
        "sessionId": "session-upg016",
        "schemaVersion": "1.0.0",
        "correlationId": "corr-fork-operator-001",
        "idempotencyKey": "idem-fork-operator-001",
        "timestamp": "2026-08-18T07:36:00Z",
        "op": "create_replay_fork",
        "payload": {
            "schemaVersion": "1.0.0",
            "forkId": "fork-operator-001",
            "sourceSequence": source_sequence,
            "reason": "operator wants a linear alternate continuation",
            "missionIntent": {
                "schemaVersion": "1.0.0",
                "missionId": "m-fork-operator-001",
                "objective": "Investigate the historical branch without reviving old authority.",
                "rawRequest": "Investigate the historical branch without reviving old authority.",
                "normalizedRequest": "investigate historical branch without reviving old authority",
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
        },
    }

    receipt = relay.execute(command)

    assert receipt["status"] == "accepted"
    assert receipt["classification"] == "accepted"
    assert receipt["streamId"] == "replay_fork-fork-operator-001"
    fork_state = comp.store.require_state("replay_fork-fork-operator-001")
    assert fork_state["newMissionId"] == "m-fork-operator-001"
    assert fork_state["historicalAuthorityReactivated"] is False
    assert comp.store.require_state("mission-m-fork-operator-001")["state"] == "draft"
    comp.close()


def test_replay_fork_command_rejects_future_source_as_authority_failure_without_mutation(tmp_path):
    from capt_runtime.composition import create_runtime

    db = str(tmp_path / "future.db")
    build_scenario(db)
    comp = create_runtime(db)
    before_head = comp.store.head_sequence()
    relay = comp.command_service("captain", "session-upg016")
    command = {
        "commandId": "cmd-fork-future",
        "operatorId": "captain",
        "sessionId": "session-upg016",
        "schemaVersion": "1.0.0",
        "correlationId": "corr-fork-future",
        "idempotencyKey": "idem-fork-future",
        "timestamp": "2026-08-18T07:38:00Z",
        "op": "create_replay_fork",
        "payload": {
            "schemaVersion": "1.0.0",
            "forkId": "fork-future",
            "sourceSequence": before_head + 100,
            "reason": "invalid future source",
            "missionIntent": {
                "schemaVersion": "1.0.0",
                "missionId": "m-fork-future",
                "objective": "This must not be created.",
                "rawRequest": "This must not be created.",
                "normalizedRequest": "this must not be created",
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
        },
    }

    receipt = relay.execute(command)

    assert receipt["status"] == "rejected"
    assert receipt["classification"] == "authority"
    assert "exceeds ledger head" in receipt["detail"]
    assert comp.store.head_sequence() == before_head
    assert comp.store.load_state("replay_fork-fork-future") is None
    assert comp.store.load_state("mission-m-fork-future") is None
    comp.close()


def _fork_command(source_sequence: int, *, command_id="cmd-fork-replay", idem="idem-fork-replay", operator="captain", session="session-upg016", reason="alternate continuation", requires_approval=False):
    return {
        "commandId": command_id,
        "operatorId": operator,
        "sessionId": session,
        "schemaVersion": "1.0.0",
        "correlationId": "corr-" + command_id,
        "idempotencyKey": idem,
        "timestamp": "2026-08-18T07:40:00Z",
        "op": "create_replay_fork",
        "payload": {
            "schemaVersion": "1.0.0",
            "forkId": "fork-replay",
            "sourceSequence": source_sequence,
            "reason": reason,
            "missionIntent": {
                "schemaVersion": "1.0.0",
                "missionId": "m-fork-replay",
                "objective": "Explore one linear historical continuation.",
                "rawRequest": "Explore one linear historical continuation.",
                "normalizedRequest": "explore one linear historical continuation",
                "scope": {},
                "constraints": [],
                "successCriteria": [],
                "terminationCriteria": [],
                "unresolvedAmbiguities": [],
                "budget": None,
                "requiresApproval": requires_approval,
                "requestedCapability": "",
                "resource": None,
                "operation": None,
                "riskClassification": "none",
                "policyReason": None,
                "taskId": None,
                "requestId": None,
            },
        },
    }


def test_replay_fork_exact_retry_is_idempotent_and_conflicting_reuse_is_rejected(tmp_path):
    from copy import deepcopy

    from capt_runtime.composition import create_runtime

    db = str(tmp_path / "idempotent.db")
    build_scenario(db)
    comp = create_runtime(db)
    source_sequence = comp.store.load_checkpoint("cp-m0a-001")["ledgerPosition"]["globalSequence"]
    relay = comp.command_service("captain", "session-upg016")
    command = _fork_command(source_sequence)

    first = relay.execute(command)
    head = comp.store.head_sequence()
    second = relay.execute(command)
    assert first["status"] == "accepted"
    assert second["status"] == "idempotent"
    assert second["classification"] == "duplicate"
    assert comp.store.head_sequence() == head

    conflict = deepcopy(command)
    conflict["payload"]["reason"] = "different semantics under same idempotency key"
    rejected = relay.execute(conflict)
    assert rejected["status"] == "rejected"
    assert rejected["classification"] == "idempotency"
    assert comp.store.head_sequence() == head
    comp.close()


def test_replay_fork_wrong_authenticated_identity_is_rejected_before_mutation(tmp_path):
    from capt_runtime.composition import create_runtime

    db = str(tmp_path / "identity.db")
    build_scenario(db)
    comp = create_runtime(db)
    source_sequence = comp.store.load_checkpoint("cp-m0a-001")["ledgerPosition"]["globalSequence"]
    before = comp.store.head_sequence()
    relay = comp.command_service("captain", "session-upg016")

    receipt = relay.execute(_fork_command(source_sequence, operator="intruder"))
    assert receipt["status"] == "rejected"
    assert receipt["classification"] == "unauthorized"
    assert comp.store.head_sequence() == before
    assert comp.store.load_state("replay_fork-fork-replay") is None
    assert comp.store.load_state("mission-m-fork-replay") is None
    comp.close()


def test_replay_fork_cannot_auto_create_or_carry_approval_authority(tmp_path):
    from capt_runtime.composition import create_runtime

    db = str(tmp_path / "approval.db")
    build_scenario(db)
    comp = create_runtime(db)
    source_sequence = comp.store.load_checkpoint("cp-m0a-001")["ledgerPosition"]["globalSequence"]
    before = comp.store.head_sequence()
    relay = comp.command_service("captain", "session-upg016")

    receipt = relay.execute(_fork_command(source_sequence, requires_approval=True))
    assert receipt["status"] == "rejected"
    assert receipt["classification"] == "authority"
    assert "cannot auto-create approval authority" in receipt["detail"]
    assert comp.store.head_sequence() == before
    assert comp.store.load_state("replay_fork-fork-replay") is None
    assert comp.store.load_state("mission-m-fork-replay") is None
    comp.close()
