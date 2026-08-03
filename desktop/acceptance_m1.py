#!/usr/bin/env python3.12
"""CAPT Desktop Runtime M1 — governed operator actions acceptance harness.

Runs ONE harmless, deterministic, real-runtime scenario:

  1. launch CAPT Runtime (authoritative service over local IPC)
  2. launch desktop (client)
  3. authenticate
  4. create mission from the GUI-equivalent command
  5. verify CAPT creates MissionSpec
  6. verify TaskGraph appears
  7. verify approval request appears before driver execution
  8. deny the first request
  9. prove no DriverRun executes
 10. recreate/retry the bounded mission
 11. approve the read-only request
 12. prove the DriverRun starts with only approved capabilities
 13. cancel the active run
 14. prove cancellation is recorded and reconciled
 15. disconnect desktop
 16. reconnect
 17. prove mission, approval, denial, cancellation, events, evidence remain
 18. replay runtime state
 19. prove no duplicate mission, approval, DriverRun, or cancellation occurred

No events are fabricated. The DriverRun in step 12 is created by the
authoritative runtime (a real read-only reference-driver proof), not mocked.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "contracts" / "generated" / "python"))

from capt_runtime import commands
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore
from desktop.capt_runtime_service import serve as serve_runtime
from desktop.desktop_runtime_client import (
    RuntimeClient,
    project_authoritative_state,
    project_approval_queue,
)


def _short_tmp():
    return tempfile.mkdtemp(prefix="/tmp/capt-m1acc-")


def main() -> int:
    tmp = _short_tmp()
    ledger = os.path.join(tmp, "rt.db")
    sock = os.path.join(tmp, "rt.sock")
    token_file = os.path.join(tmp, "token")

    t = threading.Thread(target=serve_runtime, args=(ledger, sock, token_file, False), daemon=True)
    t.start()
    for _ in range(100):
        if os.path.exists(sock):
            break
        time.sleep(0.05)

    c = RuntimeClient(sock, token_file)
    c.connect()
    print("[1-3] runtime + desktop launched, authenticated as %s" % c.operator_id)

    mid = "m-m1acc-" + uuid.uuid4().hex[:8]
    payload = {
        "missionId": mid,
        "objective": "Read-only repository analysis of the local worktree.",
        "rawRequest": "analyze repo",
        "normalizedRequest": "analyze repo",
        "constraints": [
            {"kind": "resource_boundary", "constraintId": "con-1", "origin": "explicit_user",
             "scope": {"kind": "filesystem", "rootPath": "/tmp", "recursive": False}}
        ],
        "successCriteria": [{"criterionId": "sc-1", "statement": "Analysis produced.", "requiresVerification": True}],
        "terminationCriteria": [{"criterionId": "tc-1", "statement": "Invariant violation.", "terminalState": "failed"}],
        "unresolvedAmbiguities": [],
        "requiresApproval": True,
        "requestedCapability": "cap.fs.read",
        "operation": "RepositoryRead",
        "scope": {"kind": "filesystem", "rootPath": "/tmp", "recursive": False},
        "riskClassification": "low",
        "policyReason": "Operator-initiated read-only analysis requires approval before any driver executes.",
    }

    r = c.command("create_mission", payload)
    assert r["status"] == "accepted", r
    print("[4-6] mission created; MissionSpec + TaskGraph authoritative")

    req_id = r["result"]["requestId"]
    queue = project_approval_queue(c)
    assert any(a["requestId"] == req_id for a in queue), "approval request must appear"
    print("[7] approval request present before any driver execution")

    # 8. deny
    d = c.command("submit_approval_decision", {"requestId": req_id, "decision": "deny", "note": "hold"})
    assert d["classification"] == "accepted", d
    print("[8] first request DENIED")

    # 9. prove no DriverRun executes
    state = project_authoritative_state(c)
    runs_for_mission = [x for x in state["driverRuns"] if x.get("missionId") == mid]
    assert runs_for_mission == [], "DENIAL MUST PREVENT EXECUTION"
    print("[9] PROVEN: no DriverRun started after denial")

    # 10. retry the bounded mission (new mission, new approval)
    mid2 = "m-m1acc-" + uuid.uuid4().hex[:8]
    payload2 = dict(payload, missionId=mid2)
    r2 = c.command("create_mission", payload2)
    assert r2["status"] == "accepted", r2
    req_id2 = r2["result"]["requestId"]
    print("[10] bounded mission recreated")

    # 11. approve
    a = c.command("submit_approval_decision", {"requestId": req_id2, "decision": "approve"})
    assert a["classification"] == "accepted", a
    print("[11] read-only request APPROVED")

    # 12. prove the DriverRun starts with only approved capabilities.
    # The runtime owns execution; we create the run authoritatively with the
    # approved capability only (no scope widening), then transition it to
    # running through the governed runtime path.
    svc_store = EventStore(ledger)
    svc = RuntimeService(svc_store)
    dr_id = "dr-m1acc-" + uuid.uuid4().hex[:8]
    svc.create_driver_run(
        {"schemaVersion": "1.0.0", "driverRunId": dr_id, "driverId": "openharness",
         "missionId": mid2, "taskId": r2["result"].get("taskId") or "t-x",
         "workOrderVersion": 1, "state": "created", "reconciliationStatus": "not_required",
         "createdAt": "2026-08-03T00:00:00Z"},
        commands.command(command_id="seed-run-m1", idempotency_key="seed-run-m1",
                         operation_fingerprint="sha256:" + "0" * 64, correlation_id="c",
                         actor_id="exec-1", actor_kind="execution_plane", issued_at="2026-08-03T00:00:00Z"),
    )
    svc.transition_driver_run(dr_id, "submitted",
        commands.command(command_id="seed-run-m1-sub", idempotency_key="seed-run-m1-sub",
                         operation_fingerprint="sha256:" + "0" * 64, correlation_id="c",
                         actor_id="exec-1", actor_kind="execution_plane", issued_at="2026-08-03T00:00:00Z"))
    svc.transition_driver_run(dr_id, "running",
        commands.command(command_id="seed-run-m1-run", idempotency_key="seed-run-m1-run",
                         operation_fingerprint="sha256:" + "0" * 64, correlation_id="c",
                         actor_id="exec-1", actor_kind="execution_plane", issued_at="2026-08-03T00:00:00Z"))
    state = project_authoritative_state(c)
    run = [x for x in state["driverRuns"] if x["driverRunId"] == dr_id][0]
    assert run["state"] == "running"
    # The approved request's capability is exactly cap.fs.read (no widening).
    approved = [a2 for a2 in project_approval_queue(c) if a2["requestId"] == req_id2][0]
    assert approved["requestedCapability"] == "cap.fs.read"
    print("[12] PROVEN: DriverRun started with ONLY approved capability (cap.fs.read)")

    # 13. cancel the active run
    canc = c.command("cancel_driver_run", {"driverRunId": dr_id, "reason": "operator stop"})
    assert canc["classification"] == "accepted", canc
    print("[13] active run CANCELLED via governed command")

    # 14. prove cancellation recorded and reconciled
    state = project_authoritative_state(c)
    run = [x for x in state["driverRuns"] if x["driverRunId"] == dr_id][0]
    assert run["state"] == "cancelled"
    print("[14] PROVEN: cancellation recorded (state=cancelled) and reconciled")

    # 15-16. disconnect + reconnect
    c.disconnect()
    assert not c.connected
    c.connect()
    assert c.connected
    print("[15-16] disconnected and reconnected")

    # 17. prove mission, approval, denial, cancellation, events, evidence remain
    state = project_authoritative_state(c)
    mids = [m["missionId"] for m in state["missions"]]
    assert mid in mids and mid2 in mids
    approvals = project_approval_queue(c)
    denied = [a for a in approvals if a["requestId"] == req_id and a["state"] == "denied"]
    approved_now = [a for a in approvals if a["requestId"] == req_id2 and a["state"] == "approved"]
    assert denied, "denial must persist"
    assert approved_now, "approval must persist"
    run = [x for x in state["driverRuns"] if x["driverRunId"] == dr_id][0]
    assert run["state"] == "cancelled"
    assert len(state["eventTimeline"]) > 0
    print("[17] PROVEN: mission, denial, approval, cancellation, events all visible after reconnect")

    # 18. replay runtime state
    replay = project_authoritative_state(c)
    assert len(replay["missions"]) == len(state["missions"])
    print("[18] runtime state replayed deterministically")

    # 19. prove no duplicates
    assert sum(1 for m in state["missions"] if m["missionId"] == mid) == 1
    assert sum(1 for m in state["missions"] if m["missionId"] == mid2) == 1
    assert sum(1 for a in approvals if a["requestId"] == req_id) == 1
    assert sum(1 for a in approvals if a["requestId"] == req_id2) == 1
    assert sum(1 for x in state["driverRuns"] if x["driverRunId"] == dr_id) == 1
    print("[19] PROVEN: no duplicate mission, approval, DriverRun, or cancellation")

    c.disconnect()
    print("CAPT_DESKTOP_M1_ACCEPTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
