"""Work-packet and execution-result tests for RuntimeService."""

import sys

sys.path.insert(0, ".")

import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.replay import full_replay
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore


def _metadata(actor_kind, name):
    return {
        "schemaVersion": "1.0.0",
        "commandId": "cmd-" + name,
        "idempotencyKey": "idemp-" + name,
        "operationFingerprint": "sha256:" + "0" * 64,
        "correlationId": "corr-" + name,
        "actor": {"actorId": "test-agent", "kind": actor_kind},
        "issuedAt": "2026-08-04T10:00:00Z",
        "replayPolicy": "safe",
        "attempt": 1,
    }


def _mission_metadata(name):
    return _metadata("human", name)


def _task_metadata(name):
    return _metadata("cognitive_plane", name)


def _exec_metadata(name):
    return _metadata("execution_plane", name)


def _make_mission(mission_id):
    return {
        "schemaVersion": "1.0.0",
        "missionId": mission_id,
        "rawRequest": "test mission",
        "normalizedRequest": "test mission",
        "objectives": [{"objectiveId": "obj-1", "statement": "test", "priority": 10}],
        "constraints": [],
        "successCriteria": [{"criterionId": "sc-1", "statement": "done", "requiresVerification": False}],
        "terminationCriteria": [],
        "unresolvedAmbiguities": [],
        "createdAt": "2026-08-04T10:00:00Z",
    }


def _make_task(task_id, mission_id, state="pending", attempt=0, max_attempts=3):
    return {
        "taskId": task_id,
        "missionId": mission_id,
        "title": "inspect governed target",
        "state": state,
        "consequential": False,
        "capabilityRequirements": [
            {
                "requirementId": "req-" + task_id,
                "capabilityId": "cap.repository.read",
                "operations": ["repository.read"],
                "scope": {"kind": "repository", "repositoryId": "repo-1", "refPattern": "main"},
            }
        ],
        "attempt": attempt,
        "maxAttempts": max_attempts,
    }


def _move_to_running(svc, task_id):
    for state in ("ready", "assigned", "running"):
        svc.transition_task(
            task_id,
            state,
            "test transition",
            _exec_metadata(task_id + "-" + state),
        )


def test_get_next_work_packet_selects_ready_task_with_provenance_and_snapshot():
    store = EventStore(":memory:")
    svc = RuntimeService(store)
    svc.create_mission(_make_mission("mission-wp-001"), _mission_metadata("mission-001"))
    # Pending represents a dependency that has not yet been satisfied and is not runnable.
    svc.create_task(_make_task("task-dependency", "mission-wp-001"), _task_metadata("task-dependency"))
    svc.create_task(_make_task("task-runnable", "mission-wp-001"), _task_metadata("task-runnable"))
    svc.transition_task("task-runnable", "ready", "dependencies satisfied", _exec_metadata("task-runnable-ready"))

    packet = svc.get_next_work_packet("mission-wp-001", "session-wp-001", _exec_metadata("packet-001"))

    assert packet == {
        "hasWork": True,
        "packetId": "task-runnable",
        "missionId": "mission-wp-001",
        "sessionId": "session-wp-001",
        "taskId": "task-runnable",
        "title": "inspect governed target",
        "state": "ready",
        "capabilityRequirements": _make_task("task-runnable", "mission-wp-001")["capabilityRequirements"],
        "exactNextAction": "execute_task",
        "createdAt": None,
    }


def test_get_next_work_packet_reports_no_runnable_work():
    store = EventStore(":memory:")
    svc = RuntimeService(store)
    svc.create_mission(_make_mission("mission-wp-002"), _mission_metadata("mission-002"))

    packet = svc.get_next_work_packet("mission-wp-002", "session-wp-002", _exec_metadata("packet-002"))

    assert packet == {
        "hasWork": False,
        "missionId": "mission-wp-002",
        "sessionId": "session-wp-002",
        "reason": "no_runnable_tasks",
    }


def test_get_next_work_packet_excludes_attempt_exhausted_task():
    store = EventStore(":memory:")
    svc = RuntimeService(store)
    svc.create_mission(_make_mission("mission-wp-003"), _mission_metadata("mission-003"))
    svc.create_task(
        _make_task("task-exhausted", "mission-wp-003", state="ready", attempt=3, max_attempts=3),
        _task_metadata("task-exhausted"),
    )

    packet = svc.get_next_work_packet("mission-wp-003", "session-wp-003", _exec_metadata("packet-003"))

    assert packet["hasWork"] is False
    assert packet["reason"] == "no_runnable_tasks"


def test_submit_result_records_reference_then_awaits_verification_and_replays():
    store = EventStore(":memory:")
    svc = RuntimeService(store)
    svc.create_mission(_make_mission("mission-wp-004"), _mission_metadata("mission-004"))
    svc.create_task(_make_task("task-result", "mission-wp-004"), _task_metadata("task-result"))
    _move_to_running(svc, "task-result")
    metadata = _exec_metadata("submit-result")
    result = {"status": "succeeded", "resultRef": "result://task-result/1"}

    first = svc.submit_result("task-result", result, metadata)
    version_after_first = store.aggregate_version("task-task-result")
    second = svc.submit_result("task-result", result, metadata)

    state = store.load_state("task-task-result")
    assert state is not None
    assert first["status"] == "applied"
    assert second["status"] == "idempotent"
    assert store.aggregate_version("task-task-result") == version_after_first
    assert state["state"] == "awaiting_verification"
    assert state["resultRefs"] == ["result://task-result/1"]
    event = store.read_stream("task-task-result")[-1]
    assert event["eventType"] == "TaskResultSubmitted"
    assert event["payload"] == {
        "eventType": "TaskResultSubmitted",
        "taskId": "task-result",
        "resultRef": "result://task-result/1",
        "toState": "awaiting_verification",
    }
    assert full_replay(store).aggregates["task-task-result"] == state


def test_submit_result_failure_uses_canonical_terminal_transition():
    store = EventStore(":memory:")
    svc = RuntimeService(store)
    svc.create_mission(_make_mission("mission-wp-005"), _mission_metadata("mission-005"))
    svc.create_task(_make_task("task-failure", "mission-wp-005"), _task_metadata("task-failure"))
    _move_to_running(svc, "task-failure")

    svc.submit_result(
        "task-failure",
        {"status": "failed", "resultRef": "result://task-failure/1"},
        _exec_metadata("submit-failure"),
    )

    state = store.load_state("task-task-failure")
    assert state is not None
    assert state["state"] == "failed"
    assert state["resultRefs"] == ["result://task-failure/1"]


def test_submit_result_requires_execution_or_system_authority():
    store = EventStore(":memory:")
    svc = RuntimeService(store)
    svc.create_mission(_make_mission("mission-wp-006"), _mission_metadata("mission-006"))
    svc.create_task(_make_task("task-authority", "mission-wp-006"), _task_metadata("task-authority"))
    _move_to_running(svc, "task-authority")

    with pytest.raises(AuthorityViolation):
        svc.submit_result(
            "task-authority",
            {"status": "succeeded", "resultRef": "result://task-authority/1"},
            _task_metadata("submit-authority"),
        )


def test_submit_result_rejects_embedded_result_content():
    store = EventStore(":memory:")
    svc = RuntimeService(store)
    svc.create_mission(_make_mission("mission-wp-007"), _mission_metadata("mission-007"))
    svc.create_task(_make_task("task-reference", "mission-wp-007"), _task_metadata("task-reference"))
    _move_to_running(svc, "task-reference")

    with pytest.raises(ValueError, match="only status and resultRef"):
        svc.submit_result(
            "task-reference",
            {"status": "succeeded", "resultRef": "result://task-reference/1", "observations": []},
            _exec_metadata("submit-reference"),
        )
