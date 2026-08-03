#!/usr/bin/env python3.12
"""CAPT Desktop Runtime M0 — desktop operator application (GUI surface).

A real macOS desktop application (Tk/Aqua native widget set) that is the
operator surface over the authoritative CAPT runtime. It is an UNTRUSTED
client: it connects to the local CAPT runtime service over an authenticated
Unix-domain socket and renders read-only projections. It never writes to the
CAPT ledger and never promotes driver output to authoritative state.

The view layer is deliberately thin and separated from the framework-agnostic
client (desktop_runtime_client) so the same logic is exercised headless by the
acceptance harness.

Launch:
  python3.12 desktop/desktop_app.py --sock <path> --token-file <path>
Headless (no window; used by automated acceptance/verification):
  python3.12 desktop/desktop_app.py --sock <path> --token-file <path> --headless
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from desktop.desktop_runtime_client import (
    RuntimeClient,
    project_mission_view,
    project_approval_queue,
    project_authoritative_state,
    project_cancellation_state,
)


def _fmt(value, depth: int = 0) -> str:
    """Render an arbitrary projection value as compact, readable text."""
    if isinstance(value, dict):
        if not value:
            return "{}"
        lines = []
        for k, v in value.items():
            if isinstance(v, (dict, list)):
                lines.append("%s%s:" % ("  " * depth, k))
                lines.append(_fmt(v, depth + 1))
            else:
                lines.append("%s%s: %s" % ("  " * depth, k, v))
        return "\n".join(lines)
    if isinstance(value, list):
        if not value:
            return "[]"
        return "\n".join("  " * depth + "- " + _fmt(item, depth + 1).lstrip() for item in value)
    return str(value)


class DesktopApp:
    """Owns the connection lifecycle and the rendered projection."""

    def __init__(self, sock_path: str, token_file: str) -> None:
        self.sock_path = sock_path
        self.token_file = token_file
        self.client = RuntimeClient(sock_path, token_file)
        self.identity: dict = {}
        self.view: dict = {}
        self.connected = False

    # -- lifecycle ---------------------------------------------------------

    def connect(self) -> dict:
        self.identity = self.client.connect()
        self.connected = True
        self.refresh()
        return self.identity

    def disconnect(self) -> None:
        self.client.disconnect()
        self.connected = False

    def refresh(self) -> dict:
        if not self.connected:
            raise RuntimeError("not connected")
        try:
            self.view = project_mission_view(self.client)
        except Exception:
            # M1 surfaces may run without the M0 demo mission seeded; the
            # authoritative M1 projection (refresh_m1) is the source of truth.
            self.view = {}
        return self.view

    # -- M1 governed operator actions (M1) ---------------------------------

    def refresh_m1(self) -> dict:
        """Rebuild the authoritative M1 projection from runtime state."""
        if not self.connected:
            raise RuntimeError("not connected")
        self.m1_state = project_authoritative_state(self.client)
        self.m1_approvals = project_approval_queue(self.client)
        return self.m1_state

    def create_mission(self, payload: dict, idempotency_key: Optional[str] = None) -> dict:
        return self.client.command("create_mission", payload, idempotency_key)

    def submit_approval_decision(self, request_id: str, decision: str, note: Optional[str] = None) -> dict:
        payload = {"requestId": request_id, "decision": decision}
        if note is not None:
            payload["note"] = note
        return self.client.command("submit_approval_decision", payload)

    def cancel_driver_run(self, driver_run_id: str, reason: Optional[str] = None) -> dict:
        payload = {"driverRunId": driver_run_id}
        if reason is not None:
            payload["reason"] = reason
        return self.client.command("cancel_driver_run", payload)

    def cancel_task(self, task_id: str, reason: Optional[str] = None) -> dict:
        payload = {"taskId": task_id}
        if reason is not None:
            payload["reason"] = reason
        return self.client.command("cancel_task", payload)

    # -- textual projection (shared by GUI and headless) -------------------

    def render_text(self) -> str:
        if not self.connected:
            return "DISCONNECTED"
        out = []
        out.append("=== CAPT Desktop Runtime M0 ===")
        out.append("Runtime: %s | Contract: %s" % (
            self.identity.get("runtimeVersion"),
            self.identity.get("contractSchemaVersion")))
        out.append("Ledger head: %s | chain: %s" % (
            self.identity.get("headSequence"), self.identity.get("ledgerChainDigest")))
        out.append("Integrity: %s" % self.identity.get("integrity"))
        out.append("")
        out.append("--- MissionSpec ---")
        out.append(_fmt(self.view.get("missionSpec", {})))
        out.append("")
        out.append("--- TaskGraph ---")
        out.append(_fmt(self.view.get("taskGraph", {})))
        out.append("")
        out.append("--- DriverRun ---")
        out.append(_fmt(self.view.get("driverRun", {})))
        out.append("")
        out.append("--- Capability Scopes ---")
        out.append(_fmt(self.view.get("capabilityScopes", {})))
        out.append("")
        out.append("--- Verification ---")
        out.append(_fmt(self.view.get("verification", {})))
        out.append("")
        out.append("--- ClaimGuard Disposition ---")
        out.append(_fmt(self.view.get("claimGuardDisposition", {})))
        out.append("")
        out.append("--- Event Timeline (%d events) ---" % len(self.view.get("eventTimeline", [])))
        for env in self.view.get("eventTimeline", [])[:50]:
            payload = env.get("payload", {})
            out.append("  seq=%s %s" % (env.get("globalSequence"), payload.get("eventType")))
        return "\n".join(out)


def run_headless_m1(sock_path: str, token_file: str) -> int:
    """Headless M1 run used by automated verification (no display required)."""
    app = DesktopApp(sock_path, token_file)
    ident = app.connect()
    app.refresh_m1()
    text = render_m1_text(app)
    print(text)
    assert ident.get("runtimeVersion"), "no runtime version"
    assert app.m1_state.get("missions") is not None, "no missions"
    app.disconnect()
    return 0


def render_m1_text(app: "DesktopApp") -> str:
    """Render the authoritative M1 projection as labeled, trust-tagged text."""
    if not app.connected:
        return "DISCONNECTED"
    st = getattr(app, "m1_state", {})
    approvals = getattr(app, "m1_approvals", [])
    out = []
    out.append("=== CAPT Desktop Runtime M1 (Governed Operator Actions) ===")
    out.append("Operator: %s | Runtime: %s | Contract: %s" % (
        app.client.operator_id, app.identity.get("runtimeVersion"),
        app.identity.get("contractSchemaVersion")))
    out.append("Ledger head: %s | integrity: %s" % (
        app.identity.get("headSequence"), app.identity.get("integrity")))
    out.append("")
    out.append("--- [AUTHORITATIVE] Missions (%d) ---" % len(st.get("missions", [])))
    for m in st.get("missions", []):
        out.append("  missionId=%s state=%s" % (m.get("missionId"), m.get("state")))
    out.append("")
    out.append("--- [AUTHORITATIVE] Approval Requests (%d) ---" % len(approvals))
    for a in approvals:
        out.append("  requestId=%s missionId=%s capability=%s state=%s" % (
            a.get("requestId"), a.get("missionId"), a.get("requestedCapability"), a.get("state")))
    out.append("")
    out.append("--- [AUTHORITATIVE] DriverRuns (%d) ---" % len(st.get("driverRuns", [])))
    for r in st.get("driverRuns", []):
        out.append("  driverRunId=%s missionId=%s state=%s" % (
            r.get("driverRunId"), r.get("missionId"), r.get("state")))
    out.append("")
    out.append("--- [AUTHORITATIVE] Event Timeline (%d events) ---" % len(st.get("eventTimeline", [])))
    for env in st.get("eventTimeline", [])[:50]:
        payload = env.get("payload", {})
        out.append("  seq=%s %s" % (env.get("globalSequence"), payload.get("eventType")))
    return "\n".join(out)


def run_gui_m1(sock_path: str, token_file: str) -> int:
    """Real M1 GUI launch (requires a display)."""
    try:
        import tkinter as tk
        from tkinter import scrolledtext, ttk
    except ImportError as exc:  # pragma: no cover
        print("Tk unavailable (no display?): %s" % exc, file=sys.stderr)
        return 2

    app = DesktopApp(sock_path, token_file)
    root = tk.Tk()
    root.title("CAPT Desktop Runtime — M1 Governed Operator Actions")
    root.geometry("1000x760")

    status = ttk.Label(root, text="connecting…", anchor="w")
    status.pack(fill="x", padx=6, pady=4)

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=6, pady=6)

    # Tab 1: Mission creation
    f_mission = ttk.Frame(notebook)
    notebook.add(f_mission, text="Create Mission")
    ttk.Label(f_mission, text="Objective (operator input):").pack(anchor="w", padx=6, pady=2)
    objective = ttk.Entry(f_mission, width=80)
    objective.pack(fill="x", padx=6)
    ttk.Label(f_mission, text="Target/Scope rootPath:").pack(anchor="w", padx=6, pady=2)
    scope = ttk.Entry(f_mission, width=80)
    scope.insert(0, "/tmp")
    scope.pack(fill="x", padx=6)
    requires_approval = tk.BooleanVar(value=True)
    ttk.Checkbutton(f_mission, text="Requires operator approval before execution",
                    variable=requires_approval).pack(anchor="w", padx=6, pady=2)
    mission_out = scrolledtext.ScrolledText(f_mission, wrap="word", height=10)
    mission_out.pack(fill="both", expand=True, padx=6, pady=6)

    def do_create():
        payload = {
            "missionId": "m-gui-" + __import__("uuid").uuid4().hex[:8],
            "objective": objective.get(),
            "rawRequest": objective.get(),
            "normalizedRequest": objective.get().lower(),
            "constraints": [{"kind": "resource_boundary", "constraintId": "con-1",
                             "origin": "explicit_user",
                             "scope": {"kind": "filesystem", "rootPath": scope.get(), "recursive": False}}],
            "successCriteria": [{"criterionId": "sc-1", "statement": "Objective achieved",
                                "requiresVerification": True}],
            "terminationCriteria": [{"criterionId": "tc-1", "statement": "Invariant violation",
                                     "terminalState": "failed"}],
            "unresolvedAmbiguities": [],
            "requiresApproval": requires_approval.get(),
            "requestedCapability": "cap.fs.read",
            "operation": "RepositoryRead",
            "scope": {"kind": "filesystem", "rootPath": scope.get(), "recursive": False},
            "riskClassification": "low",
            "policyReason": "Operator-initiated read-only analysis requires approval before execution.",
        }
        receipt = app.create_mission(payload)
        mission_out.delete("1.0", "end")
        mission_out.insert("1.0", _fmt(receipt))

    ttk.Button(f_mission, text="Submit Mission (real CAPT command)", command=do_create).pack(anchor="w", padx=6, pady=4)

    # Tab 2: Approvals
    f_appr = ttk.Frame(notebook)
    notebook.add(f_appr, text="Approvals")
    appr_out = scrolledtext.ScrolledText(f_appr, wrap="word")
    appr_out.pack(fill="both", expand=True, padx=6, pady=6)
    appr_req = ttk.Entry(f_appr, width=40)
    appr_req.pack(fill="x", padx=6)
    appr_note = ttk.Entry(f_appr, width=60)
    appr_note.pack(fill="x", padx=6)
    appr_btns = ttk.Frame(f_appr)
    appr_btns.pack(fill="x", padx=6, pady=4)

    def do_refresh_appr():
        app.refresh_m1()
        appr_out.delete("1.0", "end")
        appr_out.insert("1.0", render_m1_text(app))

    def do_approve():
        r = app.submit_approval_decision(appr_req.get(), "approve", appr_note.get())
        appr_out.delete("1.0", "end")
        appr_out.insert("1.0", _fmt(r))
        do_refresh_appr()

    def do_deny():
        r = app.submit_approval_decision(appr_req.get(), "deny", appr_note.get())
        appr_out.delete("1.0", "end")
        appr_out.insert("1.0", _fmt(r))
        do_refresh_appr()

    ttk.Button(appr_btns, text="Approve", command=do_approve).pack(side="left")
    ttk.Button(appr_btns, text="Deny", command=do_deny).pack(side="left")
    ttk.Button(appr_btns, text="Refresh", command=do_refresh_appr).pack(side="left")

    # Tab 3: Cancellations
    f_cancel = ttk.Frame(notebook)
    notebook.add(f_cancel, text="Cancel")
    cancel_out = scrolledtext.ScrolledText(f_cancel, wrap="word")
    cancel_out.pack(fill="both", expand=True, padx=6, pady=6)
    cancel_id = ttk.Entry(f_cancel, width=40)
    cancel_id.pack(fill="x", padx=6)
    cancel_kind = ttk.Combobox(f_cancel, values=["driver_run", "task"], state="readonly")
    cancel_kind.set("driver_run")
    cancel_kind.pack(fill="x", padx=6)

    def do_cancel():
        if cancel_kind.get() == "task":
            r = app.cancel_task(cancel_id.get(), "operator stop")
        else:
            r = app.cancel_driver_run(cancel_id.get(), "operator stop")
        cancel_out.delete("1.0", "end")
        cancel_out.insert("1.0", _fmt(r))

    ttk.Button(f_cancel, text="Cancel (governed command)", command=do_cancel).pack(anchor="w", padx=6, pady=4)

    # Tab 4: Authoritative state
    f_state = ttk.Frame(notebook)
    notebook.add(f_state, text="State")
    state_out = scrolledtext.ScrolledText(f_state, wrap="word")
    state_out.pack(fill="both", expand=True, padx=6, pady=6)

    def do_connect():
        try:
            ident = app.connect()
            app.refresh_m1()
            status.config(text="connected · operator %s · runtime %s · contract %s · head %s" % (
                app.client.operator_id, ident.get("runtimeVersion"),
                ident.get("contractSchemaVersion"), ident.get("headSequence")))
            state_out.delete("1.0", "end")
            state_out.insert("1.0", render_m1_text(app))
        except Exception as exc:  # noqa: BLE001
            status.config(text="connection failed: %s" % exc)

    def do_disconnect():
        app.disconnect()
        status.config(text="disconnected")

    controls = ttk.Frame(root)
    controls.pack(fill="x", padx=6, pady=4)
    ttk.Button(controls, text="Connect", command=do_connect).pack(side="left")
    ttk.Button(controls, text="Disconnect", command=do_disconnect).pack(side="left")

    threading.Thread(target=do_connect, daemon=True).start()
    root.mainloop()
    return 0


def run_headless(sock_path: str, token_file: str) -> int:
    """Headless run used by automated verification (no display required)."""
    app = DesktopApp(sock_path, token_file)
    ident = app.connect()
    text = app.render_text()
    print(text)
    # Sanity assertions for headless verification.
    assert ident.get("runtimeVersion"), "no runtime version"
    assert app.view.get("missionSpec"), "no mission spec"
    assert app.view.get("driverRun"), "no driver run"
    assert app.view.get("verification", {}).get("status", {}).get("kind") == "verified", \
        "verification not verified"
    app.disconnect()
    return 0


def run_gui(sock_path: str, token_file: str) -> int:
    """Real GUI launch (requires a display)."""
    try:
        import tkinter as tk
        from tkinter import scrolledtext, ttk
    except ImportError as exc:  # pragma: no cover
        print("Tk unavailable (no display?): %s" % exc, file=sys.stderr)
        return 2

    app = DesktopApp(sock_path, token_file)

    root = tk.Tk()
    root.title("CAPT Desktop Runtime — M0")
    root.geometry("900x700")

    status = ttk.Label(root, text="connecting…", anchor="w")
    status.pack(fill="x", padx=6, pady=4)

    pane = scrolledtext.ScrolledText(root, wrap="word", font=("Menlo", 11))
    pane.pack(fill="both", expand=True, padx=6, pady=6)

    def do_connect():
        try:
            ident = app.connect()
            status.config(
                text="connected · runtime %s · contract %s · head %s · integrity %s"
                % (ident.get("runtimeVersion"), ident.get("contractSchemaVersion"),
                   ident.get("headSequence"), ident.get("integrity")))
            pane.delete("1.0", "end")
            pane.insert("1.0", app.render_text())
        except Exception as exc:  # noqa: BLE001
            status.config(text="connection failed: %s" % exc)
            pane.delete("1.0", "end")
            pane.insert("1.0", "CONNECTION FAILED: %s" % exc)

    def do_disconnect():
        app.disconnect()
        status.config(text="disconnected")
        pane.delete("1.0", "end")
        pane.insert("1.0", "DISCONNECTED")

    controls = ttk.Frame(root)
    controls.pack(fill="x", padx=6, pady=4)
    ttk.Button(controls, text="Connect", command=do_connect).pack(side="left")
    ttk.Button(controls, text="Refresh", command=lambda: (
        pane.delete("1.0", "end") or pane.insert("1.0", app.render_text())
        if app.connected else None)).pack(side="left")
    ttk.Button(controls, text="Disconnect", command=do_disconnect).pack(side="left")

    # Auto-connect on launch (the vertical-slice scenario step 2-3).
    threading.Thread(target=do_connect, daemon=True).start()
    root.mainloop()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sock", required=True)
    ap.add_argument("--token-file", required=True)
    ap.add_argument("--headless", action="store_true",
                    help="run without a window (automated verification)")
    ap.add_argument("--m1", action="store_true",
                    help="run the M1 governed-operator-actions surface")
    args = ap.parse_args()
    if args.m1:
        if args.headless:
            return run_headless_m1(args.sock, args.token_file)
        return run_gui_m1(args.sock, args.token_file)
    if args.headless:
        return run_headless(args.sock, args.token_file)
    return run_gui(args.sock, args.token_file)


if __name__ == "__main__":
    raise SystemExit(main())
