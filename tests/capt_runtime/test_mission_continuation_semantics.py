from __future__ import annotations

from capt_runtime import commands
from capt_runtime.prompt_approval import request_model_prompt_approval
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore


def _meta(token: str) -> dict:
    return commands.command(
        command_id="cmd-" + token,
        idempotency_key="idem-" + token,
        operation_fingerprint=commands.fingerprint(token, {"token": token}),
        correlation_id="corr-" + token,
        actor_id="captain",
        actor_kind="human",
        issued_at="2026-08-18T13:00:00Z",
        replay_policy="never",
    )


def _intent(mission_id: str, task_id: str, objective: str) -> dict:
    return {
        "schemaVersion": "1.0.0",
        "missionId": mission_id,
        "taskId": task_id,
        "objective": objective,
        "scope": {"kind": "filesystem", "rootPath": "/tmp", "recursive": True},
        "constraints": [],
        "successCriteria": [{
            "criterionId": "sc-1", "statement": "done", "requiresVerification": True,
        }],
        "terminationCriteria": [{
            "criterionId": "tc-1", "statement": "stop", "terminalState": "failed",
        }],
        "requestedCapability": "cap.fs.read",
        "requiresApproval": False,
    }


def test_existing_mission_successor_task_does_not_recreate_mission(tmp_path):
    store = EventStore(str(tmp_path / "ledger.db"))
    svc = RuntimeService(store)
    first = _intent("m-chat-1", "m-chat-1-task-1", "first turn")
    svc.create_mission_with_approval(first, _meta("first"))
    mission_version = store.aggregate_version("mission-m-chat-1")

    second = _intent("m-chat-1", "m-chat-1-task-2", "second turn")
    result = svc.plan_task_for_existing_mission(second, _meta("second"))

    assert result["missionId"] == "m-chat-1"
    assert result["taskId"] == "m-chat-1-task-2"
    assert store.aggregate_version("mission-m-chat-1") == mission_version
    assert store.require_state("task-m-chat-1-task-2")["missionId"] == "m-chat-1"
    store.close()


def test_explicit_mission_prompt_approval_allocates_fresh_successor_task(tmp_path):
    store = EventStore(str(tmp_path / "ledger.db"))
    svc = RuntimeService(store)
    first = _intent("m-chat-2", "m-chat-2-task-1", "first turn")
    svc.create_mission_with_approval(first, _meta("seed"))

    result = request_model_prompt_approval(
        svc,
        {
            "objective": "continue the same mission",
            "targetRoot": "/tmp",
            "provider": "ollama",
            "model": "qwen",
            "missionId": "m-chat-2",
        },
        _meta("approval"),
    )

    assert result["missionId"] == "m-chat-2"
    assert result["taskId"] != "m-chat-2-task-1"
    assert result["taskId"].startswith("m-chat-2-task-")
    store.close()
