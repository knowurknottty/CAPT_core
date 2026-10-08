"""One narrowly identified legacy issue-task repair; no fabricated completion."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from desktop.capt_runtime_service import _reconcile_legacy_issue_task_marker

TASK = "m-capt-issues-20260924-live-task-1"
MID = "m-capt-issues-20260924-live"
NOW = "2026-10-08T08:00:00Z"


class FakeStore:
    def __init__(self, *, timestamp="2026-09-25T14:02:39Z", driver=False):
        self.task = {"taskId": TASK, "missionId": MID, "state": "running",
                     "assignedDriverId": "capt-node", "attempt": 1, "resultRefs": []}
        self.mission = {"missionId": MID, "state": "executing"}
        self.events = [{"eventType": "TaskTransitioned", "occurredAt": timestamp,
                        "payload": {"toState": "running"}}]
        self.driver = driver
    def load_state(self, sid):
        if sid == "task-" + TASK: return self.task
        if sid == "mission-" + MID: return self.mission
        if sid == "driverrun-existing" and self.driver:
            return {"taskId": TASK, "state": "lost"}
        return None
    def read_stream(self, sid):
        assert sid == "task-" + TASK
        return self.events
    def all_aggregates(self):
        return [("driverrun-existing", "driverrun", 1)] if self.driver else []
    def aggregate_version(self, sid):
        return 4 if sid.startswith("task-") else 3


class FakeService:
    def __init__(self, store):
        self.store, self.calls = store, []
    def transition_task(self, task_id, state, reason, metadata, expected_version):
        assert task_id == TASK and state == "suspended"
        assert expected_version == 4
        assert metadata["actor"]["kind"] == "system"
        assert "unknown" in reason
        self.store.task["state"] = state
        self.store.events.append({"eventType": "TaskTransitioned", "occurredAt": NOW,
                                  "payload": {"toState": state}})
        self.calls.append("task")
    def transition_mission(self, mission_id, state, reason, metadata, expected_version):
        assert mission_id == MID and state == "suspended"
        assert expected_version == 3
        assert "no completion" in reason
        self.store.mission["state"] = state
        self.calls.append("mission")


def runtime(**kwargs):
    store=FakeStore(**kwargs)
    svc=FakeService(store)
    return SimpleNamespace(store=store, service=svc)


def test_stale_marker_suspends_both_aggregates_without_success_or_retry():
    r=runtime()
    assert _reconcile_legacy_issue_task_marker(r, NOW)
    assert r.service.calls == ["task", "mission"]
    assert r.store.task["state"] == "suspended"
    assert r.store.mission["state"] == "suspended"
    assert not _reconcile_legacy_issue_task_marker(r, NOW)
    assert r.service.calls == ["task", "mission"]


def test_current_or_bound_execution_is_not_auto_suspended():
    for options in ({"timestamp": "2026-10-08T07:30:00Z"}, {"driver": True}):
        r=runtime(**options)
        assert not _reconcile_legacy_issue_task_marker(r, NOW)
        assert r.service.calls == []
        assert r.store.task["state"] == "running"
    r=runtime()
    r.store.task["assignedDriverId"]="other-driver"
    assert not _reconcile_legacy_issue_task_marker(r, NOW)
    assert r.service.calls == []


def test_missing_or_terminal_task_is_untouched():
    r=runtime()
    r.store.task["state"]="succeeded"
    assert not _reconcile_legacy_issue_task_marker(r, NOW)
    assert r.service.calls == []
