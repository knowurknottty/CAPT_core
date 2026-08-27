import sqlite3

import pytest

from capt_runtime.store import EventStore


FIXED_KEY_B64 = "S0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0s="
FIXED_SEALED_STATE = (
    "enc:v1:Tk5OTk5OTk5OTk5OdnCODIRI87ldq6pxWqki2XRc1rS8DTzsMSeOZ3r/"
    "3QpqvhOT/2XSIPNSUy16mwdxf7nRHv4o7DyHpbhFoQ=="
)


def test_event_store_reads_preexisting_encrypted_aggregate(tmp_path, monkeypatch):
    db = tmp_path / "runtime.db"
    seed = EventStore(str(db))
    seed.close()

    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO aggregates (stream_id, kind, version, state_json, state_digest) "
        "VALUES (?,?,?,?,?)",
        ("compat-stream", "compat", 1, FIXED_SEALED_STATE, "sha256:" + "0" * 64),
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("CAPT_STATE_KEY_B64", FIXED_KEY_B64)
    store = EventStore(str(db))
    try:
        assert store.load_state("compat-stream") == {
            "kind": "compat",
            "status": "ready",
            "value": 42,
        }
    finally:
        store.close()


def test_event_store_new_writes_remain_encrypted_at_rest(tmp_path, monkeypatch):
    import base64
    import json

    from capt_runtime import commands
    from capt_runtime.services import RuntimeService

    monkeypatch.setenv("CAPT_STATE_KEY_B64", base64.b64encode(b"K" * 32).decode("ascii"))
    db = tmp_path / "ledger" / "runtime.db"
    secret = "labs-at-rest-compat-secret"
    store = EventStore(str(db))
    svc = RuntimeService(store)
    spec = {
        "schemaVersion": "1.0.0",
        "missionId": "m-secret",
        "rawRequest": secret,
        "normalizedRequest": secret,
        "objectives": [{"objectiveId": "o1", "statement": secret, "priority": 1}],
        "constraints": [],
        "successCriteria": [{"criterionId": "s1", "statement": "done", "requiresVerification": True}],
        "terminationCriteria": [{"criterionId": "t1", "statement": "stop", "terminalState": "failed"}],
        "unresolvedAmbiguities": [],
        "taskGraphId": None,
        "createdAt": "2026-08-27T00:00:00Z",
    }
    cmd = commands.command(
        command_id="cmd-secret",
        idempotency_key="idem-secret",
        operation_fingerprint=commands.fingerprint("create_mission", {"missionId": "m-secret"}),
        correlation_id="c",
        actor_id="captain",
        actor_kind="human",
        issued_at="2026-08-27T00:00:00Z",
    )
    svc.create_mission(spec, cmd)
    store.close()

    assert secret.encode() not in db.read_bytes()

    reopened = EventStore(str(db))
    try:
        state = reopened.load_state("mission-m-secret")
        assert state is not None
        assert state["missionId"] == "m-secret"
        assert any(secret in json.dumps(event) for event in reopened.read_events())
    finally:
        reopened.close()
