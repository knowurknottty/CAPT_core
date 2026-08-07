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
from typing import Any, Dict, List, Optional

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

    # -- authoritative detail projections (read-only) ----------------------

    def get_mission_spec(self, mission_id: str) -> Optional[dict]:
        from .desktop_runtime_client import project_mission_spec
        return project_mission_spec(self.client, mission_id)

    def get_task_graph(self, task_id: str) -> Optional[dict]:
        from .desktop_runtime_client import project_task_graph
        return project_task_graph(self.client, task_id)

    def get_driver_run(self, driver_run_id: str) -> Optional[dict]:
        from .desktop_runtime_client import project_driver_run
        return project_driver_run(self.client, driver_run_id)

    def get_evidence(self, mission_id: str) -> List[dict]:
        from .desktop_runtime_client import project_evidence
        return project_evidence(self.client, mission_id)

    def get_claimguard(self, statement: str) -> dict:
        from .desktop_runtime_client import project_claimguard
        return project_claimguard(self.client, statement)

    def get_verification(self) -> dict:
        return self.client.verification()

    def get_approval_detail(self, request_id: str) -> Optional[dict]:
        for a in getattr(self, "m1_approvals", []):
            if a.get("requestId") == request_id:
                return a
        for a in self.m1_state.get("approvals", []):
            if a.get("requestId") == request_id:
                return a
        return None

    # -- GUI handler logic (shared by the visible Tk GUI and the live driver) -

    def gui_create_mission(self, raw: str, root_path: str, constraints: List[str],
                           success: str, termination: str, budget_max_events: int,
                           requires_approval: bool) -> dict:
        """Build and submit a mission from GUI fields. Returns the command receipt."""
        raw = (raw or "").strip()
        if not raw:
            raise ValueError("objective is required")
        root_path = root_path.strip() or "/tmp"
        normalized = raw.lower()
        inferred = "read-only analysis (no writes)" if ("read" in normalized or "analy" in normalized) else "unspecified"
        payload = {
            "schemaVersion": "1.0.0",
            "missionId": "m-gui-" + __import__("uuid").uuid4().hex[:8],
            "objective": raw,
            "rawRequest": raw,
            "normalizedRequest": normalized,
            "constraints": [
                {"kind": "resource_boundary", "constraintId": "con-1", "origin": "explicit_user",
                 "scope": {"kind": "filesystem", "rootPath": root_path, "recursive": False}},
            ],
            "successCriteria": [{"criterionId": "sc-1", "statement": success, "requiresVerification": True}],
            "terminationCriteria": [{"criterionId": "tc-1", "statement": termination, "terminalState": "failed"}],
            "budget": {"maxEvents": int(budget_max_events or 0)},
            "unresolvedAmbiguities": [c for c in constraints],
            "requiresApproval": bool(requires_approval),
            "requestedCapability": "cap.fs.read",
            "operation": "RepositoryRead",
            "scope": {"kind": "filesystem", "rootPath": root_path, "recursive": False},
            "riskClassification": "low",
            "policyReason": "Operator-initiated read-only analysis requires approval before execution.",
        }
        return self.create_mission(payload)

    def gui_decide(self, request_id: str, decision: str, note: Optional[str] = None) -> dict:
        return self.submit_approval_decision(request_id, decision, note)

    def gui_cancel(self, kind: str, target_id: str, reason: str = "operator stop") -> dict:
        if kind == "task":
            return self.cancel_task(target_id, reason)
        return self.cancel_driver_run(target_id, reason)

    # -- memory trigger operator controls (M1-memory) ----------------------

    def get_memory_policy(self) -> dict:
        """Read-only projection of the active MemoryTriggerPolicy."""
        return self.client._query({"op": "get_memory_policy"})["result"]

    def get_memory_state(self, mission_id: str = "") -> dict:
        """Read-only projection of memory path state for a mission."""
        return self.client._query({"op": "get_memory_state", "missionId": mission_id})["result"]

    def gui_update_memory_trigger_policy(
        self,
        *,
        retrieval_trigger_steps: Optional[int] = None,
        compression_trigger_steps: Optional[int] = None,
        checkpoint_trigger_steps: Optional[int] = None,
        consolidation_trigger_steps: Optional[int] = None,
        hard_stop_trigger_steps: Optional[int] = None,
        model_safe_limit_steps: Optional[int] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict:
        """Operator submits a memory-trigger policy change through the
        authenticated CAPT command path. The runtime validates and persists the
        authoritative policy; the desktop never mutates config/runtime directly.
        """
        payload = {}
        if retrieval_trigger_steps is not None:
            payload["retrievalTriggerSteps"] = retrieval_trigger_steps
        if compression_trigger_steps is not None:
            payload["compressionTriggerSteps"] = compression_trigger_steps
        if checkpoint_trigger_steps is not None:
            payload["checkpointTriggerSteps"] = checkpoint_trigger_steps
        if consolidation_trigger_steps is not None:
            payload["consolidationTriggerSteps"] = consolidation_trigger_steps
        if hard_stop_trigger_steps is not None:
            payload["hardStopTriggerSteps"] = hard_stop_trigger_steps
        if model_safe_limit_steps is not None:
            payload["modelSafeLimitSteps"] = model_safe_limit_steps
        if not payload:
            raise ValueError("no trigger steps provided")
        return self.client.command(
            "update_memory_trigger_policy", payload, idempotency_key
        )

    def gui_refresh_approvals(self) -> List[dict]:
        self.refresh_m1()
        return getattr(self, "m1_approvals", [])

    def gui_refresh_state(self) -> str:
        self.refresh_m1()
        return render_m1_text(self)

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


def render_m1_text(app: Any) -> str:
    """Render the authoritative M1 projection as labeled, trust-tagged text.

    Every section is explicitly tagged [AUTHORITATIVE] (sourced from CAPT) or
    [OPERATOR INPUT] / [UNTRUSTED] so untrusted content can never masquerade as
    CAPT state. The desktop never asserts its own authority.
    """
    if not app.connected:
        return "DISCONNECTED"
    st = getattr(app, "m1_state", {})
    approvals = getattr(app, "m1_approvals", [])
    out = []
    out.append("=== CAPT Desktop Runtime M1 (Governed Operator Actions) ===")
    out.append("[AUTHORITATIVE] Operator: %s | Runtime: %s | Contract: %s" % (
        app.client.operator_id, app.identity.get("runtimeVersion"),
        app.identity.get("contractSchemaVersion")))
    out.append("[AUTHORITATIVE] Ledger head: %s | chain: %s | integrity: %s" % (
        app.identity.get("headSequence"), app.identity.get("ledgerChainDigest"),
        app.identity.get("integrity")))
    out.append("")
    out.append("--- [AUTHORITATIVE] Missions (%d) ---" % len(st.get("missions", [])))
    for m in st.get("missions", []):
        out.append("  missionId=%s state=%s objective=%s" % (
            m.get("missionId"), m.get("state"), m.get("objective")))
    out.append("")
    out.append("--- [AUTHORITATIVE] Tasks (%d) ---" % len(st.get("tasks", [])))
    for t in st.get("tasks", []):
        out.append("  taskId=%s missionId=%s state=%s" % (
            t.get("taskId"), t.get("missionId"), t.get("state")))
    out.append("")
    out.append("--- [AUTHORITATIVE] Approval Requests (%d) ---" % len(approvals))
    for a in approvals:
        out.append("  requestId=%s missionId=%s taskId=%s capability=%s op=%s scope=%s risk=%s state=%s" % (
            a.get("requestId"), a.get("missionId"), a.get("taskId"),
            a.get("requestedCapability"), a.get("operation"), a.get("scope"),
            a.get("riskClassification"), a.get("state")))
    out.append("")
    out.append("--- [AUTHORITATIVE] DriverRuns (%d) ---" % len(st.get("driverRuns", [])))
    for r in st.get("driverRuns", []):
        out.append("  driverRunId=%s missionId=%s driver=%s state=%s recon=%s" % (
            r.get("driverRunId"), r.get("missionId"), r.get("driverId"),
            r.get("state"), r.get("reconciliationStatus")))
    out.append("")
    out.append("--- [AUTHORITATIVE] Verification ---")
    out.append("  %s" % _fmt(st.get("verification", {})))
    out.append("")
    out.append("--- [AUTHORITATIVE] Event Timeline (%d events) ---" % len(st.get("eventTimeline", [])))
    for env in st.get("eventTimeline", [])[:50]:
        payload = env.get("payload", {})
        out.append("  seq=%s %s" % (env.get("globalSequence"), payload.get("eventType")))
    return "\n".join(out)


def trust_tag(kind: str) -> str:
    """Return a bracketed trust tag for rendering untrusted vs authoritative content."""
    return {
        "authoritative": "[AUTHORITATIVE]",
        "operator": "[OPERATOR INPUT]",
        "untrusted": "[UNTRUSTED]",
        "evidence": "[EVIDENCE]",
        "verified": "[VERIFIED FACT]",
        "inference": "[INFERENCE]",
        "policy": "[POLICY DECISION]",
        "claimguard": "[CLAIMGUARD DISPOSITION]",
    }.get(kind, "[%s]" % kind.upper())


def sanitize_for_display(text: str, limit: int = 2000) -> str:
    """Strip terminal control sequences and cap length so untrusted content
    cannot spoof the GUI or overflow it. Returns a safe display string."""
    import re
    # Remove ANSI / terminal escape sequences.
    cleaned = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", text or "")
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0d\x0e-\x1f]", "", cleaned)
    if len(cleaned) > limit:
        cleaned = cleaned[:limit] + " …[truncated]"
    return cleaned


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
    root.geometry("1080x820")

    status = ttk.Label(root, text="connecting…", anchor="w")
    status.pack(fill="x", padx=6, pady=4)

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=6, pady=6)

    # ---- Tab 1: Mission creation -----------------------------------------
    f_mission = ttk.Frame(notebook)
    notebook.add(f_mission, text="Create Mission")
    ttk.Label(f_mission, text="[OPERATOR INPUT] Objective:").pack(anchor="w", padx=6, pady=2)
    objective = ttk.Entry(f_mission, width=90)
    objective.pack(fill="x", padx=6)
    ttk.Label(f_mission, text="[OPERATOR INPUT] Target/Scope rootPath:").pack(anchor="w", padx=6, pady=2)
    scope = ttk.Entry(f_mission, width=90)
    scope.insert(0, "/tmp")
    scope.pack(fill="x", padx=6)
    ttk.Label(f_mission, text="[OPERATOR INPUT] Explicit constraints (one per line, free text):").pack(anchor="w", padx=6, pady=2)
    constraints_in = tk.Text(f_mission, height=3)
    constraints_in.pack(fill="x", padx=6)
    ttk.Label(f_mission, text="[OPERATOR INPUT] Success criteria:").pack(anchor="w", padx=6, pady=2)
    success_in = ttk.Entry(f_mission, width=90)
    success_in.insert(0, "Objective achieved without invariant violation")
    success_in.pack(fill="x", padx=6)
    ttk.Label(f_mission, text="[OPERATOR INPUT] Termination criteria:").pack(anchor="w", padx=6, pady=2)
    term_in = ttk.Entry(f_mission, width=90)
    term_in.insert(0, "Invariant violation or objective complete")
    term_in.pack(fill="x", padx=6)
    ttk.Label(f_mission, text="[OPERATOR INPUT] Budget limit (max events, 0=unbounded):").pack(anchor="w", padx=6, pady=2)
    budget_in = ttk.Entry(f_mission, width=20)
    budget_in.insert(0, "0")
    budget_in.pack(fill="x", padx=6)
    requires_approval = tk.BooleanVar(value=True)
    ttk.Checkbutton(f_mission, text="Requires operator approval before execution",
                    variable=requires_approval).pack(anchor="w", padx=6, pady=2)
    mission_out = scrolledtext.ScrolledText(f_mission, wrap="word", height=12)
    mission_out.pack(fill="both", expand=True, padx=6, pady=6)

    def do_create():
        try:
            receipt = app.gui_create_mission(
                objective.get(), scope.get(),
                [c.strip() for c in constraints_in.get("1.0", "end").splitlines() if c.strip()],
                success_in.get().strip(), term_in.get().strip(),
                int(budget_in.get().strip() or 0), requires_approval.get())
        except ValueError as exc:
            mission_out.delete("1.0", "end")
            mission_out.insert("1.0", trust_tag("policy") + " VALIDATION ERROR: %s" % sanitize_for_display(str(exc)))
            return
        raw = objective.get().strip()
        normalized = raw.lower()
        inferred = "read-only analysis (no writes)" if "read" in normalized or "analy" in normalized else "unspecified"
        mission_out.delete("1.0", "end")
        mission_out.insert("1.0", trust_tag("authoritative") + " COMMAND RECEIPT\n" + _fmt(receipt))
        mission_out.insert("end", "\n\n[OPERATOR INPUT] raw: %s\n" % sanitize_for_display(raw))
        mission_out.insert("end", "[INFERENCE] normalized: %s\n" % sanitize_for_display(normalized))
        mission_out.insert("end", "[INFERENCE] inferred: %s\n" % sanitize_for_display(inferred))

    ttk.Button(f_mission, text="Submit Mission (real CAPT command)", command=do_create).pack(anchor="w", padx=6, pady=4)

    # ---- Tab 2: Approvals -------------------------------------------------
    f_appr = ttk.Frame(notebook)
    notebook.add(f_appr, text="Approvals")
    appr_detail = scrolledtext.ScrolledText(f_appr, wrap="word", height=10)
    appr_detail.pack(fill="both", expand=True, padx=6, pady=6)
    appr_req = ttk.Entry(f_appr, width=40)
    appr_req.pack(fill="x", padx=6)
    appr_note = ttk.Entry(f_appr, width=70)
    appr_note.pack(fill="x", padx=6)
    appr_btns = ttk.Frame(f_appr)
    appr_btns.pack(fill="x", padx=6, pady=4)

    def do_refresh_appr():
        app.refresh_m1()
        lines = [trust_tag("authoritative") + " APPROVAL QUEUE"]
        for a in app.m1_approvals:
            lines.append("  requestId=%s missionId=%s taskId=%s cap=%s op=%s scope=%s risk=%s state=%s expires=%s" % (
                a.get("requestId"), a.get("missionId"), a.get("taskId"),
                a.get("requestedCapability"), a.get("operation"), a.get("scope"),
                a.get("riskClassification"), a.get("state"), a.get("expiresAt")))
        appr_detail.delete("1.0", "end")
        appr_detail.insert("1.0", "\n".join(lines))

    def do_appr_detail():
        req = appr_req.get().strip()
        det = app.get_approval_detail(req)
        appr_detail.delete("1.0", "end")
        if not det:
            appr_detail.insert("1.0", trust_tag("policy") + " request not found: %s" % sanitize_for_display(req))
            return
        lines = [trust_tag("authoritative") + " APPROVAL REQUEST DETAIL"]
        for k in ("requestId", "missionId", "taskId", "requestedCapability", "operation",
                  "resource", "scope", "riskClassification", "policyReason", "expiresAt", "state"):
            lines.append("  %s: %s" % (k, sanitize_for_display(str(det.get(k)))))
        # Stale-state feedback: if expired, warn.
        if det.get("state") == "expired":
            lines.append(trust_tag("policy") + " STALE: request expired; approval refused")
        appr_detail.insert("1.0", "\n".join(lines))

    def do_approve():
        r = app.gui_decide(appr_req.get().strip(), "approve", appr_note.get().strip())
        appr_detail.delete("1.0", "end")
        appr_detail.insert("1.0", trust_tag("authoritative") + " DECISION RECEIPT\n" + _fmt(r))
        do_refresh_appr()

    def do_deny():
        r = app.gui_decide(appr_req.get().strip(), "deny", appr_note.get().strip())
        appr_detail.delete("1.0", "end")
        appr_detail.insert("1.0", trust_tag("authoritative") + " DECISION RECEIPT\n" + _fmt(r))
        do_refresh_appr()

    ttk.Button(appr_btns, text="Detail", command=do_appr_detail).pack(side="left")
    ttk.Button(appr_btns, text="Approve", command=do_approve).pack(side="left")
    ttk.Button(appr_btns, text="Deny", command=do_deny).pack(side="left")
    ttk.Button(appr_btns, text="Refresh", command=do_refresh_appr).pack(side="left")

    # ---- Tab 3: DriverRun & Cancellation ---------------------------------
    f_cancel = ttk.Frame(notebook)
    notebook.add(f_cancel, text="DriverRun / Cancel")
    cancel_detail = scrolledtext.ScrolledText(f_cancel, wrap="word", height=12)
    cancel_detail.pack(fill="both", expand=True, padx=6, pady=6)
    cancel_id = ttk.Entry(f_cancel, width=40)
    cancel_id.pack(fill="x", padx=6)
    cancel_kind = ttk.Combobox(f_cancel, values=["driver_run", "task"], state="readonly")
    cancel_kind.set("driver_run")
    cancel_kind.pack(fill="x", padx=6)

    def do_cancel_refresh():
        rid = cancel_id.get().strip()
        if not rid:
            cancel_detail.delete("1.0", "end")
            cancel_detail.insert("1.0", trust_tag("policy") + " enter a DriverRun or Task id")
            return
        kind = "driverrun" if cancel_kind.get() == "driver_run" else "task"
        st = app.get_driver_run(rid) if kind == "driverrun" else app.get_task_graph(rid)
        cancel_detail.delete("1.0", "end")
        if not st:
            cancel_detail.insert("1.0", trust_tag("policy") + " %s %s not found" % (kind, rid))
            return
        lines = [trust_tag("authoritative") + " %s STATE" % kind.upper()]
        for k in ("driverRunId", "taskId", "driverId", "missionId", "state",
                  "reconciliationStatus", "workOrderVersion"):
            if k in st:
                lines.append("  %s: %s" % (k, sanitize_for_display(str(st[k]))))
        cancel_detail.insert("1.0", "\n".join(lines))

    def do_cancel():
        rid = cancel_id.get().strip()
        if cancel_kind.get() == "task":
            r = app.gui_cancel("task", rid, "operator stop")
        else:
            r = app.gui_cancel("driver_run", rid, "operator stop")
        cancel_detail.delete("1.0", "end")
        cancel_detail.insert("1.0", trust_tag("authoritative") + " CANCEL RECEIPT\n" + _fmt(r))
        do_cancel_refresh()

    ttk.Button(f_cancel, text="Refresh State", command=do_cancel_refresh).pack(anchor="w", padx=6, pady=2)
    ttk.Button(f_cancel, text="Cancel (governed command)", command=do_cancel).pack(anchor="w", padx=6, pady=4)

    # ---- Tab 5: Memory Trigger (M1-memory) --------------------------------
    f_mem = ttk.Frame(notebook)
    notebook.add(f_mem, text="Memory Trigger")
    ttk.Label(f_mem, text="[OPERATOR CONTROL] Memory trigger thresholds (steps of 32,768 tokens)").pack(anchor="w", padx=6, pady=2)

    def _step_row(parent, label, default):
        ttk.Label(parent, text=label).pack(anchor="w", padx=6)
        var = tk.StringVar(value=str(default))
        ent = ttk.Entry(parent, width=10, textvariable=var)
        ent.pack(anchor="w", padx=6)
        return var

    mem_out = scrolledtext.ScrolledText(f_mem, wrap="word", height=10)
    mem_out.pack(fill="both", expand=True, padx=6, pady=6)

    v_retrieval = _step_row(f_mem, "Retrieval trigger (steps)", 8)
    v_compression = _step_row(f_mem, "Compression trigger (steps)", 8)
    v_checkpoint = _step_row(f_mem, "Checkpoint trigger (steps)", 8)
    v_consolidation = _step_row(f_mem, "Consolidation trigger (steps)", 8)
    v_hardstop = _step_row(f_mem, "Hard-stop trigger (steps)", 8)

    def _steps_ok(var, name):
        try:
            v = int(var.get().strip())
        except ValueError:
            raise ValueError("%s must be an integer step count" % name)
        if v < 1:
            raise ValueError("%s must be >= 1 step" % name)
        if v > 8:
            raise ValueError("%s exceeds model safe limit (8 steps)" % name)
        return v

    def do_mem_refresh():
        try:
            pol = app.get_memory_policy()
            st = app.get_memory_state()
        except Exception as exc:  # noqa: BLE001
            mem_out.delete("1.0", "end")
            mem_out.insert("1.0", trust_tag("policy") + " memory query failed: %s" % sanitize_for_display(str(exc)))
            return
        lines = [trust_tag("authoritative") + " MEMORY TRIGGER POLICY"]
        lines.append("  policyVersion: %s" % pol.get("policyVersion"))
        lines.append("  policyDigest: %s" % pol.get("policyDigest"))
        lines.append("  triggerIntervalTokens: %s" % pol.get("triggerIntervalTokens"))
        lines.append("  retrieval: %s steps = %s tokens" % (pol.get("retrievalTriggerSteps"), pol.get("retrievalTokens")))
        lines.append("  compression: %s steps = %s tokens" % (pol.get("compressionTriggerSteps"), pol.get("compressionTokens")))
        lines.append("  checkpoint: %s steps = %s tokens" % (pol.get("checkpointTriggerSteps"), pol.get("checkpointTokens")))
        lines.append("  consolidation: %s steps = %s tokens" % (pol.get("consolidationTriggerSteps"), pol.get("consolidationTokens")))
        lines.append("  hardStop: %s steps = %s tokens" % (pol.get("hardStopTriggerSteps"), pol.get("hardStopTokens")))
        lines.append("  modelSafeLimit: %s steps = %s tokens" % (pol.get("modelSafeLimitSteps"), pol.get("modelSafeLimitTokens")))
        lines.append("  source: %s" % pol.get("source"))
        lines.append("  memoryPathActive: %s" % st.get("memoryPathActive"))
        mem_out.delete("1.0", "end")
        mem_out.insert("1.0", "\n".join(lines))

    def do_mem_apply():
        try:
            retrieval = _steps_ok(v_retrieval, "retrieval")
            compression = _steps_ok(v_compression, "compression")
            checkpoint = _steps_ok(v_checkpoint, "checkpoint")
            consolidation = _steps_ok(v_consolidation, "consolidation")
            hardstop = _steps_ok(v_hardstop, "hardstop")
        except ValueError as exc:
            mem_out.delete("1.0", "end")
            mem_out.insert("1.0", trust_tag("policy") + " VALIDATION ERROR: %s" % sanitize_for_display(str(exc)))
            return
        receipt = app.gui_update_memory_trigger_policy(
            retrieval_trigger_steps=retrieval,
            compression_trigger_steps=compression,
            checkpoint_trigger_steps=checkpoint,
            consolidation_trigger_steps=consolidation,
            hard_stop_trigger_steps=hardstop,
            idempotency_key="mem-ui-%s" % __import__("time").time_ns(),
        )
        mem_out.delete("1.0", "end")
        if receipt.get("status") == "accepted":
            mem_out.insert("1.0", trust_tag("authoritative") + " POLICY ACCEPTED\n" + _fmt(receipt))
        else:
            mem_out.insert("1.0", trust_tag("policy") + " POLICY DENIED\n" + _fmt(receipt))
        do_mem_refresh()

    ttk.Button(f_mem, text="Refresh Policy", command=do_mem_refresh).pack(anchor="w", padx=6, pady=2)
    ttk.Button(f_mem, text="Apply Trigger Policy (governed command)", command=do_mem_apply).pack(anchor="w", padx=6, pady=4)

    # ---- Tab 4: Authoritative State / Projections ------------------------
    f_state = ttk.Frame(notebook)
    notebook.add(f_state, text="State / Evidence")
    state_out = scrolledtext.ScrolledText(f_state, wrap="word")
    state_out.pack(fill="both", expand=True, padx=6, pady=6)

    def do_connect():
        try:
            ident = app.connect()
            app.refresh_m1()
            status.config(text="connected · %s · runtime %s · contract %s · head %s" % (
                app.client.operator_id, ident.get("runtimeVersion"),
                ident.get("contractSchemaVersion"), ident.get("headSequence")))
            state_out.delete("1.0", "end")
            state_out.insert("1.0", render_m1_text(app))
        except Exception as exc:  # noqa: BLE001
            status.config(text="connection failed: %s" % exc)

    def do_disconnect():
        app.disconnect()
        status.config(text="disconnected")

    def do_refresh_state():
        app.refresh_m1()
        state_out.delete("1.0", "end")
        state_out.insert("1.0", render_m1_text(app))

    controls = ttk.Frame(root)
    controls.pack(fill="x", padx=6, pady=4)
    ttk.Button(controls, text="Connect", command=do_connect).pack(side="left")
    ttk.Button(controls, text="Disconnect", command=do_disconnect).pack(side="left")
    ttk.Button(controls, text="Refresh State", command=do_refresh_state).pack(side="left")

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
