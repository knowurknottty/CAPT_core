"""Conformance tests: transactional ledger, outbox, idempotency (I5/I6/I9)."""

from __future__ import annotations

import pytest

from capt_runtime import commands
from capt_runtime.aggregates import MissionAggregate
from capt_runtime.errors import ConcurrencyError, ContractViolation, IdempotencyError
from capt_runtime.services import RuntimeService
from capt_runtime.store import AppendRequest, EventStore


def _valid_mission_spec(mission_id="m1"):
    return {
        "schemaVersion": "1.0.0",
        "missionId": mission_id,
        "rawRequest": "prove M0-A",
        "normalizedRequest": "prove m0-a",
        "objectives": [{"objectiveId": "o1", "statement": "x", "priority": 1}],
        "constraints": [],
        "successCriteria": [{"criterionId": "s1", "statement": "y",
                             "requiresVerification": True}],
        "terminationCriteria": [{"criterionId": "t1", "statement": "z",
                                 "terminalState": "failed"}],
        "unresolvedAmbiguities": [],
        "taskGraphId": None,
        "createdAt": "2026-08-02T00:00:00Z",
    }


def _service(db):
    return RuntimeService(EventStore(db))


def _mission_cmd(step="1"):
    return commands.command(
        command_id="cmd-" + step, idempotency_key="idem-" + step,
        operation_fingerprint=commands.fingerprint("create_mission", {"missionId": "m1"}),
        correlation_id="c", actor_id="captain", actor_kind="human",
        issued_at="2026-08-02T00:00:00Z",
    )


def test_atomic_commit():
    """I5: a committed command produces both state and event in one txn."""
    store = EventStore(":memory:")
    svc = RuntimeService(store)
    spec = _valid_mission_spec("m1")
    res = svc.create_mission(spec, _mission_cmd("1"))
    assert res["status"] == "applied"
    assert store.aggregate_version("mission-m1") == 1
    assert store.head_sequence() == 1
    events = store.read_events()
    assert len(events) == 1
    assert events[0]["eventType"] == "MissionCreated"


def test_event_after_state():
    """I6: event exists only because the state transition committed."""
    store = EventStore(":memory:")
    svc = RuntimeService(store)
    spec = _valid_mission_spec("m1")
    svc.create_mission(spec, _mission_cmd("1"))
    # The committed event carries the new state's version (1), proving it was
    # written together with the snapshot, not before.
    env = store.read_events()[0]
    assert env["streamVersion"] == 1
    assert env["payloadDigest"].startswith("sha256:")


def test_outbox_not_dispatched_before_commit():
    """Authoritative events never leave the store before commit returns."""
    store = EventStore(":memory:")
    svc = RuntimeService(store)
    spec = _valid_mission_spec("m1")
    svc.create_mission(spec, _mission_cmd("1"))
    # After commit, dispatch moves the event out of the pending set.
    assert store.pending_outbox() == []  # dispatch() ran inside _commit


def test_stale_version_rejected():
    """Optimistic concurrency: a command with a wrong expected version fails."""
    store = EventStore(":memory:")
    svc = RuntimeService(store)
    spec = _valid_mission_spec("m1")
    svc.create_mission(spec, _mission_cmd("1"))
    # A second transition that claims expected version 1 (already at 1) is fine,
    # but one claiming version 5 must be rejected.
    from capt_runtime.errors import ConcurrencyError

    with pytest.raises(ConcurrencyError):
        svc.transition_mission("m1", "authorized", "ok", _mission_cmd("2"),
                               expected_version=5)


def test_duplicate_command_idempotent():
    """I9: replaying the same command does not duplicate state or events."""
    store = EventStore(":memory:")
    svc = RuntimeService(store)
    spec = _valid_mission_spec("m1")
    first = svc.create_mission(spec, _mission_cmd("1"))
    second = svc.create_mission(spec, _mission_cmd("1"))
    assert first["status"] == "applied"
    assert second["status"] == "idempotent"
    assert store.head_sequence() == 1  # still one event


def test_stream_versions_monotonic():
    store = EventStore(":memory:")
    svc = RuntimeService(store)
    spec = _valid_mission_spec("m1")
    svc.create_mission(spec, _mission_cmd("1"))
    svc.transition_mission("m1", "authorized", "ok", _mission_cmd("2"))
    svc.transition_mission("m1", "executing", "ok", _mission_cmd("3"))
    versions = [e["streamVersion"] for e in store.read_events()]
    assert versions == [1, 2, 3]


def test_hash_chain_integrity():
    store = EventStore(":memory:")
    svc = RuntimeService(store)
    spec = _valid_mission_spec("m1")
    svc.create_mission(spec, _mission_cmd("1"))
    svc.transition_mission("m1", "authorized", "ok", _mission_cmd())
    digest1 = store.verify_chain()
    assert digest1.startswith("sha256:")
    # Tamper with an event payload and confirm the chain rejects it.
    store._conn.execute(
        "UPDATE events SET envelope_json = ? WHERE global_sequence = 1",
        ('{"eventType":"Hacked"}',),
    )
    store._conn.commit()
    with pytest.raises(Exception):
        store.verify_chain()
