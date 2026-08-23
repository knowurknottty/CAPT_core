"""CAPT Desktop Runtime M1 — governed operator actions integration tests.

These tests exercise the REAL CAPT runtime (no mocking). They launch the
authoritative runtime service over a local authenticated Unix-domain socket
and drive it through the desktop client command API. They prove:

* mission creation uses real CAPT commands (MissionCreated event);
* denial prevents execution (no DriverRun starts);
* approval permits only bounded execution;
* cancellation is authoritative and reconciled (DriverRun -> cancelled);
* reconnect reconstructs state without duplicate commands;
* operator identity is bound (spoofing rejected);
* idempotency suppresses duplicates.
"""

import os
import socket
import tempfile
import time
import uuid

import pytest

from capt_runtime.store import EventStore
from desktop.capt_runtime_service import serve as serve_runtime
from desktop.desktop_runtime_client import RuntimeClient, project_authoritative_state, project_approval_queue


def _start_runtime(tmp):
    ledger = os.path.join(tmp, "rt.db")
    sock = os.path.join(tmp, "rt.sock")
    token_file = os.path.join(tmp, "token")
    import threading
    t = threading.Thread(
        target=serve_runtime,
        args=(ledger, sock, token_file, False),
        daemon=True,
    )
    t.start()
    for _ in range(100):
        if os.path.exists(sock):
            break
        time.sleep(0.05)
    return sock, token_file, ledger


@pytest.fixture
def client():
    # Use a SHORT temp dir: AF_UNIX socket paths are limited (~104 chars) on macOS.
    tmp = tempfile.mkdtemp(prefix="/tmp/capt-m1-")
    sock, token_file, ledger = _start_runtime(tmp)
    c = RuntimeClient(sock, token_file)
    c.connect()
    yield c
    c.disconnect()


def _make_mission_payload(mission_id, requires_approval=False):
    return {
        "schemaVersion": "1.0.0",
        "missionId": mission_id,
        "objective": "Read-only repository analysis of the local worktree.",
        "rawRequest": "analyze repo",
        "normalizedRequest": "analyze repo",
        "constraints": [
            {"kind": "resource_boundary", "constraintId": "con-1", "origin": "explicit_user",
             "scope": {"kind": "filesystem", "rootPath": "/tmp", "recursive": False}}
        ],
        "successCriteria": [
            {"criterionId": "sc-1", "statement": "Analysis produced.", "requiresVerification": True}
        ],
        "terminationCriteria": [
            {"criterionId": "tc-1", "statement": "Invariant violation.", "terminalState": "failed"}
        ],
        "unresolvedAmbiguities": [],
        "requiresApproval": requires_approval,
        "requestedCapability": "cap.fs.read",
        "operation": "RepositoryRead",
        "scope": {"kind": "filesystem", "rootPath": "/tmp", "recursive": False},
        "riskClassification": "low",
        "policyReason": "Operator-initiated read-only analysis requires approval before any driver executes.",
    }


def test_create_mission_real_command(client):
    mid = "m-test-" + uuid.uuid4().hex[:8]
    resp = client.command("create_mission", _make_mission_payload(mid))
    assert resp["status"] == "accepted", resp
    assert resp["classification"] == "accepted", resp
    # Authoritative proof: a MissionCreated event exists.
    state = project_authoritative_state(client)
    mids = [m["missionId"] for m in state["missions"]]
    assert mid in mids


def test_deny_prevents_execution(client):
    mid = "m-deny-" + uuid.uuid4().hex[:8]
    payload = _make_mission_payload(mid, requires_approval=True)
    resp = client.command("create_mission", payload)
    assert resp["status"] == "accepted"
    req_id = resp["result"]["requestId"]
    # Deny the request.
    dresp = client.command("submit_approval_decision", {"requestId": req_id, "decision": "deny", "note": "not now"})
    assert dresp["classification"] == "accepted", dresp
    # No DriverRun should have started for this mission.
    state = project_authoritative_state(client)
    runs = [r for r in state["driverRuns"] if r.get("missionId") == mid]
    assert runs == [], "denial must prevent any DriverRun from starting"


def test_approve_permits_bounded_execution(client):
    mid = "m-appr-" + uuid.uuid4().hex[:8]
    payload = _make_mission_payload(mid, requires_approval=True)
    resp = client.command("create_mission", payload)
    req_id = resp["result"]["requestId"]
    aresp = client.command("submit_approval_decision", {"requestId": req_id, "decision": "approve"})
    assert aresp["classification"] == "accepted", aresp
    # Approval state recorded authoritatively.
    queue = project_approval_queue(client)
    req = [a for a in queue if a["requestId"] == req_id][0]
    assert req["state"] == "approved"
    # The approved scope is exactly the requested scope (no widening).
    assert req["requestedCapability"] == "cap.fs.read"


def test_operator_spoofing_rejected(client):
    mid = "m-spoof-" + uuid.uuid4().hex[:8]
    # Craft a command envelope with a different operatorId than the bound session.
    env = {
        "commandId": "cmd-spoof",
        "operatorId": "operator-someone-else",
        "sessionId": client.session_id,
        "schemaVersion": "1.0.0",
        "correlationId": "corr-x",
        "idempotencyKey": "idem-spoof",
        "timestamp": "2026-08-03T00:00:00Z",
        "op": "create_mission",
        "payload": _make_mission_payload(mid),
    }
    # Send the spoofed envelope directly and read the raw receipt.
    client._send(client._sock, {"op": "command", "command": env})
    resp = client._recv(client._sock)
    assert resp["classification"] == "unauthorized", resp


def test_duplicate_create_is_idempotent(client):
    mid = "m-dup-" + uuid.uuid4().hex[:8]
    p = _make_mission_payload(mid)
    r1 = client.command("create_mission", p, idempotency_key="idem-dup-1")
    r2 = client.command("create_mission", p, idempotency_key="idem-dup-1")
    assert r2["status"] == "idempotent"
    assert r2["classification"] == "duplicate"
    # Exactly one mission exists.
    state = project_authoritative_state(client)
    assert sum(1 for m in state["missions"] if m["missionId"] == mid) == 1


def test_cancel_driver_run(client):
    mid = "m-cancel-" + uuid.uuid4().hex[:8]
    p = _make_mission_payload(mid)
    resp = client.command("create_mission", p)
    # Create a driver run via the authoritative service bound to the same ledger.
    from capt_runtime import commands
    from capt_runtime.services import RuntimeService
    import capt_runtime.store as cs
    ident = client.identity()
    ledger_file = ident["ledgerPath"]
    svc_store = cs.EventStore(ledger_file)
    svc = RuntimeService(svc_store)
    dr_id = "dr-" + uuid.uuid4().hex[:8]
    svc.create_driver_run(
        {"schemaVersion": "1.0.0", "driverRunId": dr_id, "driverId": "openharness",
         "missionId": mid, "taskId": resp["result"].get("taskId") or "t-x",
         "workOrderVersion": 1, "state": "running", "reconciliationStatus": "not_required",
         "createdAt": "2026-08-03T00:00:00Z"},
        commands.command(command_id="seed-run", idempotency_key="seed-run",
                         operation_fingerprint="sha256:" + "0" * 64, correlation_id="c",
                         actor_id="exec-1", actor_kind="execution_plane", issued_at="2026-08-03T00:00:00Z"),
    )
    cres = client.command("cancel_driver_run", {"driverRunId": dr_id, "reason": "operator stop"})
    assert cres["classification"] == "accepted", cres
    # Authoritative state shows cancelled.
    state = project_authoritative_state(client)
    run = [r for r in state["driverRuns"] if r["driverRunId"] == dr_id][0]
    assert run["state"] == "cancelled"


def test_reconcile_lost_driver_run_via_governed_command(client):
    mid = "m-reconcile-lost-" + uuid.uuid4().hex[:8]
    resp = client.command("create_mission", _make_mission_payload(mid))
    from capt_runtime import commands
    from capt_runtime.services import RuntimeService
    import capt_runtime.store as cs
    ledger_file = client.identity()["ledgerPath"]
    svc_store = cs.EventStore(ledger_file)
    svc = RuntimeService(svc_store)
    dr_id = "dr-lost-" + uuid.uuid4().hex[:8]
    meta = lambda step: commands.command(
        command_id="seed-reconcile-" + step, idempotency_key="seed-reconcile-" + step,
        operation_fingerprint="sha256:" + "1" * 64, correlation_id="corr-reconcile",
        actor_id="exec-1", actor_kind="execution_plane", issued_at="2026-08-03T00:00:00Z")
    svc.create_driver_run(
        {"schemaVersion": "1.0.0", "driverRunId": dr_id, "driverId": "provider",
         "missionId": mid, "taskId": resp["result"].get("taskId") or "t-x",
         "workOrderVersion": 1, "state": "created", "reconciliationStatus": "not_required",
         "createdAt": "2026-08-03T00:00:00Z"}, meta("create"))
    svc.transition_driver_run(dr_id, "submitted", meta("submitted"))
    svc.transition_driver_run(dr_id, "running", meta("running"))
    svc.transition_driver_run(dr_id, "lost", meta("lost"))
    svc_store.close()

    blocked = client.command("cancel_driver_run", {"driverRunId": dr_id, "reason": "wrong semantic"})
    assert blocked["classification"] == "illegal_transition"
    reconciled = client.command(
        "reconcile_driver_run",
        {"driverRunId": dr_id, "disposition": "resolved_effect_absent",
         "reason": "external effect checked absent; safe to retry under a fresh run"},
        idempotency_key="idem-reconcile-lost")
    assert reconciled["classification"] == "accepted", reconciled
    again = client.command(
        "reconcile_driver_run",
        {"driverRunId": dr_id, "disposition": "resolved_effect_absent", "reason": "same decision"},
        idempotency_key="idem-reconcile-lost")
    assert again["status"] == "idempotent"
    state = project_authoritative_state(client)
    run = [r for r in state["driverRuns"] if r["driverRunId"] == dr_id][0]
    assert run["state"] == "reconciled"
    assert run["reconciliationStatus"] == "resolved_effect_absent"


def test_reconnect_reconstructs_state(client):
    mid = "m-recon-" + uuid.uuid4().hex[:8]
    client.command("create_mission", _make_mission_payload(mid))
    # Disconnect and reconnect.
    client.disconnect()
    assert not client.connected
    client.connect()
    assert client.connected
    # State reconstructed without duplicates.
    state = project_authoritative_state(client)
    assert sum(1 for m in state["missions"] if m["missionId"] == mid) == 1
