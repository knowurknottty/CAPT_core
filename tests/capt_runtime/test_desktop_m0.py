#!/usr/bin/env python3.12
"""Unit + integration tests for the CAPT Desktop Runtime M0 vertical slice.

These tests drive a REAL local CAPT runtime service (not a mock). They assert:
- the runtime service seeds a faithful read-only demo mission;
- the desktop client authenticates and reads authoritative state;
- the projection contains every required M0 panel;
- disconnect/reconnect reconstructs an identical view (no duplicate exec);
- unauthenticated IPC is rejected;
- the desktop never mutates the ledger (head sequence stable across reads).
"""
from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "contracts" / "generated" / "python"))

from desktop.desktop_runtime_client import RuntimeClient, project_mission_view

pytestmark = pytest.mark.skipif(
    not (REPO / "capt_runtime").exists(),
    reason="CAPT_core runtime not present",
)


def _wait_sock(sock: Path, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if sock.exists():
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.settimeout(1.0)
                s.connect(str(sock))
                s.close()
                return
            except OSError:
                pass
        time.sleep(0.2)
    raise TimeoutError("runtime socket did not appear: %s" % sock)


@pytest.fixture()
def runtime():
    tmp = Path(tempfile.mkdtemp(prefix="capt-desktop-test-"))
    ledger = tmp / "runtime.db"
    sock = tmp / "runtime.sock"
    tok = tmp / "token.txt"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO)
    proc = subprocess.Popen(
        [sys.executable, str(REPO / "desktop" / "capt_runtime_service.py"),
         "--ledger", str(ledger), "--sock", str(sock),
         "--token-file", str(tok), "--seed"],
        cwd=str(REPO), env=env,
    )
    try:
        _wait_sock(sock)
        yield {"ledger": ledger, "sock": sock, "token": tok}
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def test_authenticated_connect_and_identity(runtime):
    client = RuntimeClient(str(runtime["sock"]), str(runtime["token"]))
    ident = client.connect()
    assert ident["runtimeVersion"]
    assert ident["contractSchemaVersion"] == "1.0.0"
    assert ident["integrity"] == "ok"
    assert ident["ledgerChainDigest"].startswith("sha256:")
    client.disconnect()


def test_projection_contains_all_m0_panels(runtime):
    client = RuntimeClient(str(runtime["sock"]), str(runtime["token"]))
    client.connect()
    view = project_mission_view(client)
    assert view["missionSpec"]["missionId"] == "m-desktop-m0-demo"
    assert view["taskGraph"]["taskId"] == "t-desktop-m0-demo"
    assert view["driverRun"]["state"] == "completed"
    assert view["capabilityScopes"]["grant"] is not None
    assert view["capabilityScopes"]["lease"] is not None
    assert len(view["eventTimeline"]) > 0
    assert view["claimGuardDisposition"]["verdict"] in ("accepted", "rejected")
    assert view["verification"]["status"]["kind"] == "verified"
    assert view["verification"]["trust"] == "capt_authoritative"
    client.disconnect()


def test_disconnect_reconnect_no_duplicate_execution(runtime):
    client = RuntimeClient(str(runtime["sock"]), str(runtime["token"]))
    client.connect()
    view1 = project_mission_view(client)
    head1 = client.identity()["headSequence"]
    d1 = hashlib.sha256(json.dumps(view1, sort_keys=True, default=str).encode()).hexdigest()
    client.disconnect()

    client2 = RuntimeClient(str(runtime["sock"]), str(runtime["token"]))
    client2.connect()
    view2 = project_mission_view(client2)
    head2 = client2.identity()["headSequence"]
    d2 = hashlib.sha256(json.dumps(view2, sort_keys=True, default=str).encode()).hexdigest()
    client2.disconnect()

    assert head1 == head2, "head advanced across read-only reconnect"
    assert d1 == d2, "view digest changed across reconnect (duplicate execution?)"


def test_unauthenticated_ipc_rejected(runtime):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(3.0)
    s.connect(str(runtime["sock"]))
    RuntimeClient._send(s, {"token": "definitely-wrong"})
    resp = RuntimeClient._recv(s)
    s.close()
    assert resp.get("ok") is False


def test_read_only_does_not_advance_ledger(runtime):
    client = RuntimeClient(str(runtime["sock"]), str(runtime["token"]))
    client.connect()
    head_before = client.identity()["headSequence"]
    # Perform many reads; none should mutate authoritative state.
    for _ in range(5):
        project_mission_view(client)
    head_after = client.identity()["headSequence"]
    client.disconnect()
    assert head_before == head_after
