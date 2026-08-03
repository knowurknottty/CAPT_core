#!/usr/bin/env python3.12
"""CAPT Desktop Runtime M0 — acceptance harness (the vertical-slice proof).

Drives the full Gate 5 scenario against a REAL local CAPT runtime service:

  1. Start the runtime service (seeds a read-only demo mission via real CAPT).
  2. Launch the desktop client; authenticate the IPC session.
  3. Display runtime identity/version + contract version + health.
  4. Select the read-only demo mission.
  5. Display MissionSpec, TaskGraph, DriverRun, capability scopes, event
     timeline, evidence, verification result, ClaimGuard disposition.
  6. Disconnect the desktop process.
  7. Keep CAPT runtime state intact (service still owns the ledger).
  8. Relaunch + reconnect the desktop.
  9. Reconstruct the same view from authoritative runtime data.
 10. Prove no duplicate execution and no state mutation from view rendering.

Exit 0 = CAPT_DESKTOP_M0_PROVEN path satisfied (evidence written). Non-zero
on any assertion failure. The harness is the acceptance proof; it does not
mock the runtime and does not hard-code a successful mission.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "contracts" / "generated" / "python"))

from desktop.desktop_runtime_client import RuntimeClient, project_mission_view

EVIDENCE: dict = {"scenario": "Gate5 vertical slice", "steps": [], "assertions": []}


def step(name: str, **fields) -> None:
    EVIDENCE["steps"].append({"step": name, **fields})


def assert_ok(name: str, cond: bool, detail: object = "") -> None:
    EVIDENCE["assertions"].append({"name": name, "ok": bool(cond), "detail": str(detail)[:400]})
    if not cond:
        raise AssertionError("%s: %s" % (name, detail))


def wait_for_sock(sock_path: Path, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if sock_path.exists():
            # give the server a moment to listen
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.settimeout(1.0)
                s.connect(str(sock_path))
                s.close()
                return
            except OSError:
                pass
        time.sleep(0.2)
    raise TimeoutError("runtime socket did not appear: %s" % sock_path)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="capt-desktop-m0-"))
    ledger = tmp / "runtime.db"
    sock = tmp / "runtime.sock"
    token_file = tmp / "token.txt"

    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO)

    svc = subprocess.Popen(
        [sys.executable, str(REPO / "desktop" / "capt_runtime_service.py"),
         "--ledger", str(ledger), "--sock", str(sock),
         "--token-file", str(token_file), "--seed"],
        cwd=str(REPO), env=env,
    )
    try:
        wait_for_sock(sock)
        step("runtime_service_started", pid=svc.pid, ledger=str(ledger))

        # --- first desktop session ---
        client = RuntimeClient(str(sock), str(token_file))
        identity = client.connect()
        step("desktop_connected", identity=identity)
        assert_ok("runtime_identity_present",
                  bool(identity.get("runtimeVersion")) and bool(identity.get("contractSchemaVersion")),
                  identity)
        assert_ok("runtime_health_ok", identity.get("integrity") == "ok",
                  identity.get("integrity"))
        assert_ok("ledger_chain_present", bool(identity.get("ledgerChainDigest")),
                  identity.get("ledgerChainDigest"))

        view1 = project_mission_view(client)
        step("mission_view_rendered", missionId=view1["missionSpec"]["missionId"],
             driverRunState=view1["driverRun"]["state"],
             claimGuard=view1["claimGuardDisposition"])

        # Required panels must be populated from authoritative state.
        assert_ok("mission_spec_present", view1["missionSpec"] is not None)
        assert_ok("task_graph_present", view1["taskGraph"] is not None)
        assert_ok("driver_run_present", view1["driverRun"] is not None)
        assert_ok("capability_scopes_present",
                  view1["capabilityScopes"]["grant"] is not None
                  and view1["capabilityScopes"]["lease"] is not None)
        assert_ok("event_timeline_present", len(view1["eventTimeline"]) > 0,
                  len(view1["eventTimeline"]))
        assert_ok("claimguard_disposition_present",
                  view1["claimGuardDisposition"]["verdict"] in ("accepted", "rejected"))
        # Verification: the demo ran a real reference-driver proof; the
        # verification result is CAPT-authored and must be 'verified'.
        assert_ok("verification_present",
                  view1["verification"] is not None
                  and view1["verification"]["status"]["kind"] == "verified",
                  view1["verification"])

        # Capture a digest of the authoritative view to prove reconnect
        # reconstructs the SAME state (no duplicate execution / no mutation).
        view1_digest = hashlib.sha256(
            json.dumps(view1, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        head1 = identity["headSequence"]

        # --- disconnect the desktop process (runtime keeps running) ---
        client.disconnect()
        step("desktop_disconnected", connected=client.connected)
        assert_ok("runtime_still_alive_after_disconnect", svc.poll() is None,
                  "service exited: %s" % svc.poll())

        # --- relaunch + reconnect the desktop ---
        client2 = RuntimeClient(str(sock), str(token_file))
        identity2 = client2.connect()
        step("desktop_reconnected", identity=identity2)
        view2 = project_mission_view(client2)
        view2_digest = hashlib.sha256(
            json.dumps(view2, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        head2 = identity2["headSequence"]
        client2.disconnect()

        # No duplicate execution: reconnect is a pure read; head sequence and
        # the reconstructed view digest are unchanged.
        assert_ok("no_duplicate_execution_head_stable", head1 == head2,
                  "head1=%s head2=%s" % (head1, head2))
        assert_ok("view_reconstructed_identical", view1_digest == view2_digest,
                  "view1=%s view2=%s" % (view1_digest[:16], view2_digest[:16]))

        # No state mutation from view rendering: the ledger head sequence did
        # not advance merely from the desktop reading it.
        assert_ok("no_mutation_from_render", head2 == head1,
                  "head advanced during read-only render")

        # Adversarial: an unauthenticated client must be rejected.
        bad = RuntimeClient(str(sock), str(token_file))
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(3.0)
        s.connect(str(sock))
        from desktop.desktop_runtime_client import RuntimeClient as _RC
        _RC._send(s, {"token": "wrong-token"})
        resp = _RC._recv(s)
        s.close()
        assert_ok("unauthenticated_ipc_rejected", resp.get("ok") is False,
                  resp)

        EVIDENCE["result"] = "CAPT_DESKTOP_M0_PROVEN"
        EVIDENCE["ledger"] = str(ledger)
        EVIDENCE["view1Digest"] = view1_digest
        EVIDENCE["headSequence"] = head1
        out = REPO / "desktop" / "acceptance_m0_evidence.json"
        out.write_text(json.dumps(EVIDENCE, indent=2, default=str))
        print(json.dumps(EVIDENCE, indent=2, default=str))
        return 0
    finally:
        if svc.poll() is None:
            svc.terminate()
            try:
                svc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                svc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
