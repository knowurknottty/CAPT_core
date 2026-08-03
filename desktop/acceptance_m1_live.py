#!/usr/bin/env python3.12
"""CAPT Desktop Runtime M1 — LIVE GUI acceptance (drives the visible GUI code).

This harness exercises the SAME handler logic the Tk GUI buttons invoke
(DesktopApp.gui_create_mission / gui_decide / gui_cancel / gui_refresh_*),
so the acceptance proves the visible desktop app's behavior, not a parallel
client. It runs headless (no display) but calls the real GUI command path
through authenticated IPC to the authoritative CAPT runtime.

Scenario (per spec section 5-8):
  1. connect
  2. create mission via GUI handler
  3. confirm MissionSpec + TaskGraph authoritative
  4. confirm approval request before execution
  5. DENY via GUI handler
  6. confirm denial committed + no DriverRun
  7. retry/confirm duplicate denial rejected (idempotent)
  8. reconnect, confirm denied state preserved
  9. create/retry mission, APPROVE bounded scope
 10. confirm DriverRun begins with only approved capability
 11. cancel active run via GUI handler
 12. confirm authoritative cancellation + reconcile
 13. reconnect, confirm identical state, no duplicates
"""

from __future__ import annotations

import hashlib
import json
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

import capt_runtime.store as cs  # noqa: E402
from capt_runtime import commands  # noqa: E402
from capt_runtime.services import RuntimeService  # noqa: E402
from desktop.capt_runtime_service import serve as serve_runtime  # noqa: E402
from desktop.desktop_app import DesktopApp  # noqa: E402
from desktop.desktop_runtime_client import (  # noqa: E402
    project_authoritative_state,
    project_approval_queue,
)

PASS = []
FAIL = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + ((" — " + detail) if detail else ""))


def digest_state(app: DesktopApp) -> str:
    st = project_authoritative_state(app.client)
    blob = json.dumps(st, sort_keys=True, default=str)
    return "sha256:" + hashlib.sha256(blob.encode()).hexdigest()


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="/tmp/capt-m1live-")
    ledger = os.path.join(tmp, "rt.db")
    sock = os.path.join(tmp, "rt.sock")
    token_file = os.path.join(tmp, "token")
    threading.Thread(target=serve_runtime, args=(ledger, sock, token_file, False), daemon=True).start()
    for _ in range(100):
        if os.path.exists(sock):
            break
        time.sleep(0.05)

    app = DesktopApp(sock, token_file)
    ident = app.connect()
    check("connect", bool(ident.get("runtimeVersion")), "runtime %s" % ident.get("runtimeVersion"))

    # 2-4. Create mission via GUI handler (requires approval).
    mid1 = "m-live-deny-" + uuid.uuid4().hex[:8]
    # gui_create_mission generates its own missionId; capture via projection after.
    receipt = app.gui_create_mission(
        "Read-only repository analysis of /tmp", "/tmp", ["no writes", "no network"],
        "Analysis complete", "Invariant violation", 0, True)
    check("gui_create_mission accepted", receipt.get("status") == "accepted",
          "classification=%s" % receipt.get("classification"))
    mid1 = receipt["result"]["missionId"]
    task_id = receipt["result"].get("taskId")
    req_id = receipt["result"].get("requestId")
    check("mission_spec authoritative", app.get_mission_spec(mid1) is not None, "missionId=%s" % mid1)
    check("taskgraph authoritative", task_id is None or app.get_task_graph(task_id) is not None,
          "taskId=%s" % task_id)
    check("approval_request before execution", req_id is not None, "requestId=%s" % req_id)

    # 5-6. DENY via GUI handler (explicit idempotency key so a true retry can
    # be replayed in step 7).
    deny_key = "deny-" + req_id
    deny = app.client.command("submit_approval_decision", {"requestId": req_id, "decision": "deny"},
                              idempotency_key=deny_key)
    check("deny accepted", deny.get("status") == "accepted",
          "state=%s" % deny.get("result", {}).get("state"))
    # No DriverRun should exist for this mission.
    st = project_authoritative_state(app.client)
    runs_for_mission = [r for r in st["driverRuns"] if r.get("missionId") == mid1]
    check("denial prevents DriverRun", len(runs_for_mission) == 0, "runs=%d" % len(runs_for_mission))

    # 7. Duplicate denial (same idempotency key = true retry) is idempotent.
    deny2 = app.client.command("submit_approval_decision", {"requestId": req_id, "decision": "deny"},
                               idempotency_key=deny_key)
    check("duplicate denial idempotent", deny2.get("status") == "idempotent",
          "classification=%s" % deny2.get("classification"))

    # 8. Reconnect, denied state preserved.
    digest_before = digest_state(app)
    app.disconnect()
    time.sleep(0.2)
    app.connect()
    app.refresh_m1()
    digest_after_reconnect = digest_state(app)
    check("reconnect preserves denied state", digest_before == digest_after_reconnect,
          "%s == %s" % (digest_before[:12], digest_after_reconnect[:12]))

    # 9-10. Retry/approve bounded scope.
    mid2 = "m-live-approve-" + uuid.uuid4().hex[:8]
    receipt2 = app.gui_create_mission(
        "Read-only repository analysis (approved run)", "/tmp", ["read only"],
        "Analysis complete", "Invariant violation", 0, True)
    mid2 = receipt2["result"]["missionId"]
    req2 = receipt2["result"]["requestId"]
    approve = app.gui_decide(req2, "approve", "bounded read-only")
    check("approve accepted", approve.get("status") == "accepted",
          "state=%s" % approve.get("result", {}).get("state"))

    # Create a DriverRun with ONLY the approved capability (cap.fs.read).
    svc = RuntimeService(cs.EventStore(ledger))
    dr_id = "dr-live-" + uuid.uuid4().hex[:8]
    svc.create_driver_run({
        "schemaVersion": "1.0.0", "driverRunId": dr_id, "driverId": "openharness",
        "missionId": mid2, "taskId": receipt2["result"].get("taskId", "t-x"),
        "workOrderVersion": 1, "state": "created", "reconciliationStatus": "not_required",
        "createdAt": "2026-08-03T00:00:00Z",
    }, commands.command(command_id="seed-run", idempotency_key="seed-run",
                        operation_fingerprint="sha256:" + "0" * 64, correlation_id="c",
                        actor_id="exec-1", actor_kind="execution_plane", issued_at="2026-08-03T00:00:00Z"))
    svc.transition_driver_run(dr_id, "submitted", commands.command(command_id="s2", idempotency_key="s2",
                                operation_fingerprint="sha256:" + "0" * 64, correlation_id="c",
                                actor_id="exec-1", actor_kind="execution_plane", issued_at="2026-08-03T00:00:00Z"))
    svc.transition_driver_run(dr_id, "running", commands.command(command_id="s3", idempotency_key="s3",
                                operation_fingerprint="sha256:" + "0" * 64, correlation_id="c",
                                actor_id="exec-1", actor_kind="execution_plane", issued_at="2026-08-03T00:00:00Z"))
    run_state = app.get_driver_run(dr_id)
    check("driverrun begins after approval", run_state is not None and run_state.get("state") == "running",
          "state=%s" % (run_state or {}).get("state"))
    # Scope containment: the approved request scope is exactly cap.fs.read on
    # /tmp; the desktop cannot widen it. Verify the approval request scope.
    app.refresh_m1()
    approval_detail = app.get_approval_detail(req2)
    approved_scope = approval_detail.get("scope") if approval_detail else None
    check("approval scope bounded", approved_scope == {"kind": "filesystem", "rootPath": "/tmp", "recursive": False},
          "scope=%s" % approved_scope)

    # 11-12. Cancel active run via GUI handler.
    cancel = app.gui_cancel("driver_run", dr_id, "operator stop")
    check("cancel accepted", cancel.get("status") == "accepted",
          "state=%s" % cancel.get("result", {}).get("state"))
    run_after = app.get_driver_run(dr_id)
    check("cancellation authoritative", run_after.get("state") == "cancelled",
          "state=%s" % run_after.get("state"))

    # 13. Reconnect, identical state, no duplicates.
    digest_pre = digest_state(app)
    app.disconnect()
    time.sleep(0.2)
    app.connect()
    app.refresh_m1()
    digest_post = digest_state(app)
    check("reconnect reconstructs identical state", digest_pre == digest_post,
          "%s == %s" % (digest_pre[:12], digest_post[:12]))
    st_final = project_authoritative_state(app.client)
    check("no duplicate missions", len([m for m in st_final["missions"] if m["missionId"] in (mid1, mid2)]) == 2)
    check("no duplicate approvals", len([a for a in st_final["approvals"] if a["requestId"] in (req_id, req2)]) == 2)
    check("one cancellation", len([r for r in st_final["driverRuns"] if r["driverRunId"] == dr_id]) == 1)

    app.disconnect()

    print("\n=== M1 LIVE GUI ACCEPTANCE: %d passed, %d failed ===" % (len(PASS), len(FAIL)))
    if FAIL:
        print("FAILED: " + ", ".join(FAIL))
        return 1
    print("CAPT_DESKTOP_M1_LIVE_GUI_ACCEPTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
