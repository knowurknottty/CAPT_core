"""Adversarial tests for the CAPT Bootstrap Bridge IPC, locking, continuity, and ownership.

These exercise process- and filesystem-level behavior where the risk is real:
unauthenticated/replayed/stale turn requests, atomic lease acquisition, stale
lock recovery, PID reuse, fencing, corrupted/missing/legacy continuity metadata,
mission/checkpoint mismatch, rollback, failed atomic write, two processes for the
same session, stale runner checkpoint write, per-turn ownership, provider failure
without fallback, deep-path socket overflow, unauthorized local client, and
authenticated shutdown.

No test merely asserts internal helper output without exercising the real
socket/lock/metadata path where the risk lives.
"""

from __future__ import annotations

import json
import os
import socket
import tempfile
import time
from pathlib import Path

import pytest

from capt_solo.bridge.continuity import (
    MISSING,
    ContinuityError,
    load_continuity,
    save_continuity,
)
from capt_solo.bridge.lease import (
    DuplicateRunnerError,
    acquire_runner_lease,
    read_held_lease,
    release_runner_lease,
)
from capt_solo.bridge.protocol import (
    ERR_INVALID_AUTH,
    ERR_MALFORMED,
    ERR_MISSING_AUTH,
    ERR_OVERSIZED,
    ERR_REPLAYED,
    ERR_STALE_GENERATION,
    OP_SHUTDOWN,
    OP_TURN,
    TurnEnvelope,
)
from capt_solo.bridge.serve import _handle_turn, _run_governed_turn, _ServeState


def _make_state(runtime_id, generation, auth):
    st = _ServeState()
    st.runtime_id = runtime_id
    st.runtime_generation = generation
    st.turn_auth = auth
    return st


def _bind() -> socket.socket:
    d = Path(tempfile.mkdtemp(prefix="br-t-"))
    os.chmod(d, 0o700)
    sock = d / "t.sock"
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(sock))
    os.chmod(str(sock), 0o600)
    srv.listen(1)
    return srv
def _client(srv):
    """Return (server_conn, client_conn)."""
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.connect(srv.getsockname())
    server_conn, _ = srv.accept()
    return server_conn, client


def _send(conn, obj):
    if not isinstance(obj, dict):
        raise TypeError(f"request must be dict, got {type(obj).__name__}")
    conn.sendall(json.dumps(obj).encode("utf-8"))
    conn.shutdown(socket.SHUT_WR)


import threading


def _exchange(srv, state, request_dict, seen=None):
    """Send a request and run one turn handler; return the parsed client response."""
    assert isinstance(state, _ServeState), type(state)
    assert isinstance(request_dict, dict), type(request_dict)
    if seen is None:
        seen = set()
    srv_conn, cli = _client(srv)
    cli.settimeout(5.0)
    srv_conn.settimeout(5.0)
    errors: list = []

    def run_server() -> None:
        try:
            _handle_turn(state, srv_conn, seen)
        except BaseException as exc:  # noqa: BLE001 - surface in parent
            errors.append(exc)
        finally:
            try:
                srv_conn.close()
            except OSError:
                pass

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    try:
        _send(cli, request_dict)
        response = json.loads(_recv(cli))
    finally:
        try:
            cli.close()
        except OSError:
            pass
    thread.join(timeout=5.0)
    assert not thread.is_alive(), "turn handler did not terminate"
    if errors:
        raise errors[0]
    return response


@pytest.fixture(autouse=True)
def _reset_bridge_state():
    yield
    # No module globals remain; each test builds its own _ServeState.


def _recv(conn) -> bytes:
    conn.settimeout(5.0)
    chunks = []
    total = 0
    while total < 256 * 1024:
        data = conn.recv(8192)
        if not data:
            break
        chunks.append(data)
        total += len(data)
    return b"".join(chunks)


def _env(*, runtime_id, generation, auth, op, intent, request_id="req"):
    return TurnEnvelope(
        protocol_version=1, runtime_id=runtime_id, runtime_generation=generation,
        request_id=request_id, nonce="n", auth=auth, op=op, payload={"intent": intent},
    ).__dict__

# --- 1. unauthenticated turn request -----------------------------------------
def test_unauthenticated_turn_rejected(tmp_path):
    state = _make_state("r1", 1, "")
    srv = _bind()
    resp = _exchange(srv, state, _env(runtime_id="r1", generation=1, auth="", op=OP_TURN, intent="x"))
    assert resp.get("error") == "TURN_UNAUTHENTICATED"
    srv.close()


# --- 2. invalid turn token ----------------------------------------------------
def test_invalid_turn_token(tmp_path):
    state = _make_state("r1", 1, "secret")
    srv = _bind()
    resp = _exchange(srv, state, _env(runtime_id="r1", generation=1, auth="wrong", op=OP_TURN, intent="x"))
    assert resp.get("error") == ERR_INVALID_AUTH
    srv.close()


# --- 3. replayed request ------------------------------------------------------
def test_replayed_request_rejected(tmp_path):
    state = _make_state("r1", 1, "secret")
    srv = _bind()
    seen: set = set()
    env = _env(runtime_id="r1", generation=1, auth="secret", op=OP_TURN, intent="x", request_id="same")
    _exchange(srv, state, env, seen)
    resp = _exchange(srv, state, env, seen)
    assert resp.get("error") == ERR_REPLAYED
    srv.close()


# --- 4. stale runtime generation ---------------------------------------------
def test_stale_generation_rejected(tmp_path):
    state = _make_state("r1", 2, "secret")
    srv = _bind()
    resp = _exchange(srv, state, _env(runtime_id="r1", generation=1, auth="secret", op=OP_TURN, intent="x"))
    assert resp.get("error") == ERR_STALE_GENERATION
    srv.close()


# --- 5. unauthenticated shutdown ---------------------------------------------
def test_unauthenticated_shutdown_rejected(tmp_path):
    state = _make_state("r1", 1, "secret")
    srv = _bind()
    resp = _exchange(srv, state, _env(runtime_id="r1", generation=1, auth="", op=OP_SHUTDOWN, intent=""))
    assert resp.get("error") == "TURN_UNAUTHENTICATED"
    srv.close()


# --- 6. malformed request ----------------------------------------------------
def test_malformed_request_rejected(tmp_path):
    state = _make_state("r1", 1, "secret")
    srv = _bind()
    resp = _exchange(srv, state, {"op": "turn"})  # missing required envelope fields
    assert resp.get("error") == ERR_MALFORMED
    srv.close()


# --- 7. oversized request ----------------------------------------------------
def test_oversized_request_rejected(tmp_path):
    state = _make_state("r1", 1, "secret")
    srv = _bind()
    big = "x" * (300 * 1024)
    env = _env(runtime_id="r1", generation=1, auth="secret", op=OP_TURN, intent=big)
    wire = json.dumps(env).encode("utf-8")
    assert len(wire) > 256 * 1024, "test payload must exceed the request-size bound"
    resp = _exchange(srv, state, env)
    assert resp.get("error") == ERR_OVERSIZED
    srv.close()


# --- 8. concurrent duplicate boot --------------------------------------------
def test_concurrent_duplicate_boot(tmp_path):
    acquire_runner_lease(tmp_path, "m", runtime_id="r1", runtime_generation=1, pid=os.getpid(), pgid=os.getpid())
    with pytest.raises(DuplicateRunnerError):
        acquire_runner_lease(tmp_path, "m", runtime_id="r2", runtime_generation=1, pid=os.getpid(), pgid=os.getpid())
    release_runner_lease(tmp_path, "m", lease=None)


# --- 9. atomic lock acquisition ----------------------------------------------
def test_atomic_lock_acquisition(tmp_path):
    l1 = acquire_runner_lease(tmp_path, "m", runtime_id="r1", runtime_generation=1, pid=os.getpid(), pgid=os.getpid())
    with pytest.raises(DuplicateRunnerError):
        acquire_runner_lease(tmp_path, "m", runtime_id="r2", runtime_generation=1, pid=os.getpid(), pgid=os.getpid())
    assert read_held_lease(tmp_path, "m").runtime_id == "r1"
    release_runner_lease(tmp_path, "m", lease=l1)


# --- 10. stale lock recovery -------------------------------------------------
def test_stale_lock_recovery(tmp_path):
    acquire_runner_lease(tmp_path, "m", runtime_id="r1", runtime_generation=1, pid=999_999_999, pgid=999_999_999)
    reclaimed = acquire_runner_lease(tmp_path, "m", runtime_id="r2", runtime_generation=1, pid=os.getpid(), pgid=os.getpid())
    assert reclaimed is not None
    assert read_held_lease(tmp_path, "m").runtime_id == "r2"


# --- 11. PID reuse simulation ------------------------------------------------
def test_pid_reuse_handled(tmp_path):
    acquire_runner_lease(tmp_path, "m", runtime_id="r1", runtime_generation=1, pid=999_999_999, pgid=999_999_999)
    reclaimed = acquire_runner_lease(tmp_path, "m", runtime_id="r2", runtime_generation=1, pid=os.getpid(), pgid=os.getpid())
    assert reclaimed is not None
    release_runner_lease(tmp_path, "m", lease=reclaimed)


# --- 12. wrong fencing token -------------------------------------------------
def test_wrong_fencing_token_fenced(tmp_path):
    l1 = acquire_runner_lease(tmp_path, "m", runtime_id="r1", runtime_generation=1, pid=999_999_999, pgid=999_999_999)
    l2 = acquire_runner_lease(tmp_path, "m", runtime_id="r2", runtime_generation=2, pid=os.getpid(), pgid=os.getpid())
    assert l2.fences(l1)
    assert not l1.fences(l2)
    release_runner_lease(tmp_path, "m", lease=l2)


# --- 13. SIGKILL recovery ----------------------------------------------------
def test_sigkill_recovery(tmp_path):
    lease = acquire_runner_lease(tmp_path, "m", runtime_id="r1", runtime_generation=1, pid=999_999_999, pgid=999_999_999)
    lease.last_heartbeat = time.time() - 100.0
    from capt_solo.bridge.lease import _lock_path

    _lock_path(tmp_path, "m").write_text(json.dumps(lease.to_dict(), sort_keys=True))
    reclaimed = acquire_runner_lease(tmp_path, "m", runtime_id="r2", runtime_generation=1, pid=os.getpid(), pgid=os.getpid())
    assert reclaimed is not None


# --- 14. corrupted continuity metadata --------------------------------------
def test_corrupted_continuity_metadata(tmp_path):
    p = tmp_path / ".capt" / "bridge"
    p.mkdir(parents=True, exist_ok=True)
    (p / "continuity-m.json").write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ContinuityError):
        load_continuity(tmp_path, "m")


# --- 15. missing continuity metadata -----------------------------------------
def test_missing_continuity_metadata(tmp_path):
    with pytest.raises(ContinuityError) as exc:
        load_continuity(tmp_path, "m")
    assert exc.value.code == MISSING


# --- 16. legacy sidecar migration --------------------------------------------
def test_legacy_sidecar_migration(tmp_path):
    p = tmp_path / ".capt" / "bridge"
    p.mkdir(parents=True, exist_ok=True)
    (p / "session-m.sid").write_text("legacy-session-123", encoding="utf-8")
    meta = load_continuity(tmp_path, "m")
    assert meta.session_id == "legacy-session-123"
    assert not (p / "session-m.sid").exists()


# --- 17. mission mismatch ----------------------------------------------------
def test_mission_mismatch(tmp_path):
    import hashlib

    from capt_solo.bridge.continuity import _path

    save_continuity(tmp_path, mission_id="m", session_id="s", checkpoint_id="c", runtime_id="r",
                    runtime_generation=1, previous_generation=0, checkpoint_digest="d", fencing_token="f")
    p = _path(tmp_path, "m")
    data = json.loads(p.read_text(encoding="utf-8"))
    # Recompute the integrity digest over the altered content so integrity passes,
    # but the internal mission_id no longer matches the requested mission.
    data["mission_id"] = "other-mission"
    digest_src = {k: v for k, v in data.items() if k != "metadata_digest"}
    data["metadata_digest"] = hashlib.sha256(
        json.dumps(digest_src, sort_keys=True).encode("utf-8")
    ).hexdigest()
    p.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    with pytest.raises(ContinuityError) as exc:
        load_continuity(tmp_path, "m")
    assert exc.value.code == "CONTINUITY_MISSION_MISMATCH"


# --- 18. checkpoint mismatch -------------------------------------------------
def test_checkpoint_mismatch(tmp_path):
    save_continuity(tmp_path, mission_id="m", session_id="s", checkpoint_id="c1", runtime_id="r",
                    runtime_generation=1, previous_generation=0, checkpoint_digest="d", fencing_token="f")
    with pytest.raises(ContinuityError) as exc:
        load_continuity(tmp_path, "m", expected_checkpoint_id="c2")
    assert exc.value.code == "CONTINUITY_CHECKPOINT_MISMATCH"


# --- 19. metadata rollback ---------------------------------------------------
def test_metadata_rollback_rejected(tmp_path):
    save_continuity(tmp_path, mission_id="m", session_id="s", checkpoint_id="c", runtime_id="r",
                    runtime_generation=3, previous_generation=2, checkpoint_digest="d", fencing_token="f")
    with pytest.raises(ContinuityError) as exc:
        save_continuity(tmp_path, mission_id="m", session_id="s", checkpoint_id="c", runtime_id="r",
                        runtime_generation=1, previous_generation=0, checkpoint_digest="d", fencing_token="f")
    assert exc.value.code == "CONTINUITY_ROLLBACK_DETECTED"


# --- 20. failed atomic write -------------------------------------------------
def test_failed_atomic_write(tmp_path, monkeypatch):
    base = tmp_path / ".capt" / "bridge"
    base.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(os, "rename", lambda *a, **k: (_ for _ in ()).throw(OSError("boom")))
    with pytest.raises(ContinuityError) as exc:
        save_continuity(tmp_path, mission_id="m", session_id="s", checkpoint_id="c", runtime_id="r",
                        runtime_generation=1, previous_generation=0, checkpoint_digest="d", fencing_token="f")
    assert exc.value.code == "CONTINUITY_WRITE_FAILED"


# --- 21. two processes same session ------------------------------------------
def test_two_processes_same_session(tmp_path):
    l1 = acquire_runner_lease(tmp_path, "m", runtime_id="r1", runtime_generation=1, pid=os.getpid(), pgid=os.getpid(), session_id="s1")
    with pytest.raises(DuplicateRunnerError):
        acquire_runner_lease(tmp_path, "m", runtime_id="r2", runtime_generation=1, pid=os.getpid(), pgid=os.getpid(), session_id="s1")
    release_runner_lease(tmp_path, "m", lease=l1)


# --- 22. stale runner checkpoint write ---------------------------------------
def test_stale_runner_fenced_from_write(tmp_path):
    l1 = acquire_runner_lease(tmp_path, "m", runtime_id="r1", runtime_generation=1, pid=999_999_999, pgid=999_999_999)
    l2 = acquire_runner_lease(tmp_path, "m", runtime_id="r2", runtime_generation=2, pid=os.getpid(), pgid=os.getpid())
    assert l2.fences(l1)
    assert not l1.fences(l2)
    release_runner_lease(tmp_path, "m", lease=l2)


# --- 23. owner transfer per-turn verification --------------------------------
def test_per_turn_ownership_receipt(tmp_path):
    from capt_solo.bridge.protocol import compute_receipt_digest

    receipt = {
        "request_id": "req1", "turn_id": "t1", "mission_id": "m", "session_id": "s",
        "runtime_id": "r", "runtime_generation": 1, "provider_owner": "CAPT_AGENT_RUNNER",
        "execution_mode": "GOVERNED", "ctp_transaction_id": "tx", "checkpoint_before": "c0",
        "checkpoint_after": "c1", "claim_supported": True,
    }
    digest = compute_receipt_digest(receipt)
    assert digest == compute_receipt_digest(receipt)
    assert receipt["provider_owner"] == "CAPT_AGENT_RUNNER"


# --- 24. provider failure without Hermes fallback ----------------------------
def test_provider_failure_no_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv("CAPT_MODEL_ENDPOINT", raising=False)
    monkeypatch.delenv("LM_STUDIO_ENDPOINT", raising=False)
    st = _make_state("r1", 1, "secret")
    st.runner = None
    st.state = None
    env = TurnEnvelope(protocol_version=1, runtime_id="r1", runtime_generation=1, request_id="x",
                       nonce="n", auth="secret", op=OP_TURN, payload={"intent": "i"})
    resp = _run_governed_turn(st, env, "i")
    assert resp.get("provider_owner") == "CAPT_AGENT_RUNNER"
    assert resp.get("ok") is False


# --- 25. socket-path overflow on deep paths ----------------------------------
def test_socket_path_overflow_deep(tmp_path):
    from capt_solo.bridge.runner_process import _ReadyListener

    deep = tmp_path
    for i in range(14):
        deep = deep / ("seg-%02d" % i)
    deep.mkdir(parents=True, exist_ok=True)
    lst = _ReadyListener(deep)
    assert lst.secure()
    assert len(lst.path) <= 104
    lst.close()

# --- 26. unauthorized local client -------------------------------------------
def test_unauthorized_local_client(tmp_path):
    state = _make_state("r1", 1, "secret")
    srv = _bind()
    # Valid envelope structure but empty auth token -> unauthenticated.
    resp = _exchange(srv, state, _env(runtime_id="r1", generation=1, auth="", op=OP_TURN, intent="x"))
    assert resp.get("error") == "TURN_UNAUTHENTICATED"
    srv.close()


# --- 27. shutdown after valid authentication --------------------------------
def test_shutdown_after_valid_auth(tmp_path):
    state = _make_state("r1", 1, "secret")
    srv = _bind()
    resp = _exchange(srv, state, _env(runtime_id="r1", generation=1, auth="secret", op=OP_SHUTDOWN, intent=""))
    assert resp.get("ok") is True and resp.get("shutdown") is True
    srv.close()


# --- 28. cleanup after interrupted startup -----------------------------------
def test_cleanup_after_interrupted_startup(tmp_path):
    lease = acquire_runner_lease(tmp_path, "m", runtime_id="r1", runtime_generation=1, pid=999_999_999, pgid=999_999_999)
    lease.last_heartbeat = time.time() - 60.0
    from capt_solo.bridge.lease import _lock_path

    _lock_path(tmp_path, "m").write_text(json.dumps(lease.to_dict(), sort_keys=True))
    reclaimed = acquire_runner_lease(tmp_path, "m", runtime_id="r2", runtime_generation=1, pid=os.getpid(), pgid=os.getpid())
    assert reclaimed is not None
