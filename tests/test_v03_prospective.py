"""CAPT Solo v0.3 — Prospective Memory tests.

Covers: pending, blocked, ready, resolution, expiration, session surfacing,
project-bootstrap surfacing.
"""

import pytest

from capt_solo.lifecycle.prospective import (
    ProspectiveStore, PROSPECTIVE_KINDS, PROSPECTIVE_STATUSES,
)
from capt_solo.memory.engine import MemoryEngine


@pytest.fixture
def pros(mem_engine):
    return ProspectiveStore(mem_engine)


def test_prospective_kinds_and_statuses():
    assert "task" in PROSPECTIVE_KINDS
    assert "blocker" in PROSPECTIVE_KINDS
    assert "release_gate" in PROSPECTIVE_KINDS
    assert "pending" in PROSPECTIVE_STATUSES
    assert "resolved" in PROSPECTIVE_STATUSES


def test_prospective_create_pending(pros):
    iid = pros.create("fix flaky test", kind="task", namespace="proj")
    assert iid
    i = pros.get(iid)
    assert i.status == "pending"
    assert i.kind == "task"


def test_prospective_resolve(pros):
    iid = pros.create("do x", kind="task")
    ok = pros.resolve(iid, reason="done")
    assert ok is True
    assert pros.get(iid).status == "resolved"
    assert pros.get(iid).resolved_at is not None


def test_prospective_blocked_and_ready(pros):
    iid = pros.create("wait for api", kind="blocker", status="blocked")
    assert pros.get(iid).status == "blocked"
    # become ready
    pros.set_status(iid, "ready")
    assert pros.get(iid).status == "ready"


def test_prospective_expire(pros):
    iid = pros.create("old task", kind="task")
    pros.expire(iid)
    assert pros.get(iid).status == "expired"


def test_prospective_list_filters(pros):
    pros.create("a", kind="task", namespace="proj")
    pros.create("b", kind="blocker", namespace="proj")
    pros.create("c", kind="task", namespace="other")
    pending_proj = pros.list(namespace="proj", status="pending")
    assert len(pending_proj) == 2
    ready = pros.list(status="ready")
    assert ready == []


def test_prospective_surfacing_at_session_begin(pros):
    pros.create("unfinished work", kind="task", namespace="proj", status="pending")
    surfaced = pros.surface_for("session begin", namespace="proj")
    assert len(surfaced) == 1
    assert surfaced[0]["description"] == "unfinished work"


def test_prospective_surfacing_at_bootstrap(pros):
    pros.create("gate", kind="release_gate", namespace="proj", status="pending")
    boot = pros.surface_for("bootstrap", namespace="proj")
    assert any(i["kind"] == "release_gate" for i in boot)


def test_prospective_cancelled(pros):
    iid = pros.create("drop this", kind="task")
    pros.set_status(iid, "cancelled")
    assert pros.get(iid).status == "cancelled"
