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

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from desktop.desktop_runtime_client import RuntimeClient, project_mission_view


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
        self.view = project_mission_view(self.client)
        return self.view

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
    args = ap.parse_args()
    if args.headless:
        return run_headless(args.sock, args.token_file)
    return run_gui(args.sock, args.token_file)


if __name__ == "__main__":
    raise SystemExit(main())
