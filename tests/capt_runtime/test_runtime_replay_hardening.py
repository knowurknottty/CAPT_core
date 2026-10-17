"""Replay and RuntimeService single-owner regression gates."""
from __future__ import annotations

from copy import deepcopy
import socket
import subprocess
import sys

import pytest

from capt_runtime.errors import IntegrityViolation
from capt_runtime.replay import ReplayState, _apply
from desktop.capt_runtime_service import _acquire_runtime_state_lock


def test_driver_dispatch_boundary_replays_and_rejects_drift():
    state = ReplayState()
    sid = "driverrun-dr-hardening"
    run = {
        "driverRunId": "dr-hardening", "driverId": "provider",
        "missionId": "m-hardening", "taskId": "t-hardening",
        "workOrderVersion": 1, "state": "created",
    }
    created = {
        "streamId": sid, "streamVersion": 1, "eventId": "e1",
        "payload": {"eventType": "DriverRunCreated", "driverRun": run},
    }
    _apply(state, created)
    boundaries = ["request_started", "response_started", "response_completed"]
    before = "not_dispatched"
    for i, boundary in enumerate(boundaries, 2):
        event = {
            "streamId": sid, "streamVersion": i, "eventId": f"e{i}",
            "payload": {
                "eventType": "DriverRunDispatchBoundaryRecorded",
                "driverRunId": "dr-hardening", "dispatchBoundary": boundary,
                "previousDispatchBoundary": before,
                "recordedAt": "2026-10-17T09:00:00Z",
            },
        }
        if i == 2:
            valid_second = deepcopy(event)
        _apply(state, event)
        before = boundary
    assert state.aggregates[sid]["dispatchBoundary"] == "response_completed"
    assert state.aggregates[sid]["providerHttpRequestAttempts"] == 1
    bad = deepcopy(valid_second)
    bad["streamVersion"] = 5
    bad["payload"]["previousDispatchBoundary"] = "not_dispatched"
    with pytest.raises(IntegrityViolation):
        _apply(state, bad)

def test_runtime_lock_rejects_second_process_before_socket_or_token_mutation(tmp_path):
    ledger = tmp_path / "runtime.db"
    token = tmp_path / "runtime.token"
    token.write_text("unchanged-private-token", encoding="utf-8")
    sockpath = tmp_path / "runtime.sock"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(sockpath))
    listener.listen(1)
    held = _acquire_runtime_state_lock(str(ledger))
    try:
        competitor = subprocess.run(
            [sys.executable, "-m", "desktop.capt_runtime_service",
             "--ledger", str(ledger), "--sock", str(sockpath),
             "--token-file", str(token)],
            capture_output=True, text=True, timeout=10,
        )
        assert competitor.returncode != 0
        assert "already owns state lock" in competitor.stderr
        assert token.read_text(encoding="utf-8") == "unchanged-private-token"
        assert sockpath.is_socket()
    finally:
        held.close()
        listener.close()
    reacquired = _acquire_runtime_state_lock(str(ledger))
    reacquired.close()

def test_stale_socket_is_reclaimed_under_exclusive_runtime_lock(tmp_path):
    import threading
    import time
    from desktop.capt_runtime_service import serve
    from desktop.desktop_runtime_client import RuntimeClient

    ledger = tmp_path / "runtime.db"
    sockpath = tmp_path / "runtime.sock"
    token = tmp_path / "runtime.token"
    stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stale.bind(str(sockpath))
    stale.close()
    assert sockpath.is_socket()

    server = threading.Thread(
        target=serve, args=(str(ledger), sockpath, str(token), False),
        daemon=True,
    )
    server.start()
    client = RuntimeClient(str(sockpath), str(token), connect_timeout=1.0)
    ready = False
    try:
        for _ in range(100):
            if token.exists() and sockpath.exists():
                try:
                    client.connect()
                    ready = True
                    break
                except (OSError, RuntimeError, ValueError):
                    pass
            time.sleep(0.05)
        assert ready, "runtime failed to recover a stale socket"
        assert client.identity()["integrity"] == "ok"
        result = client.command("shutdown", {}, "stale-socket-shutdown")
        assert result["status"] in ("accepted", "idempotent")
    finally:
        client.disconnect()
    server.join(timeout=5)
    assert not server.is_alive()
    assert not sockpath.exists()
