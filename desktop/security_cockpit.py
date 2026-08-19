#!/usr/bin/env python3
"""Standalone CAPT Security Closure Cockpit (CAPT-UPG-019).

Evaluates the existing CAPT security gate for a supplied profile/evidence/source
SHA and renders the result without converting it into release authority or a
global security claim.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from capt_runtime.security_gate import evaluate_security_gate, load_evidence, load_profile
from capt_ui.operator.security_cockpit import project_security_cockpit


def load_cockpit(profile: Path, evidence: Path, source_sha: str) -> Dict[str, Any]:
    gate = evaluate_security_gate(
        load_profile(profile),
        load_evidence(evidence),
        source_sha=source_sha,
    )
    return project_security_cockpit(gate.to_dict())


def run_window(cockpit: Dict[str, Any]) -> None:
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("CAPT Security Closure Cockpit")
    root.geometry("1200x760")

    counts = cockpit.get("counts") or {}
    header = ttk.Label(
        root,
        text=(
            "Security gate %s | source %s | PASS %s | FAIL %s | NOT_VERIFIED %s | N/A %s"
            % (
                cockpit.get("gateDecision"), cockpit.get("sourceSha"),
                counts.get("pass", 0), counts.get("fail", 0),
                counts.get("not_verified", 0), counts.get("not_applicable", 0),
            )
        ),
    )
    header.pack(fill="x", padx=10, pady=8)

    columns = ("id", "status", "severity", "blocking", "title")
    tree = ttk.Treeview(root, columns=columns, show="headings")
    for column, width in (("id", 110), ("status", 120), ("severity", 90), ("blocking", 85), ("title", 600)):
        tree.heading(column, text=column.upper())
        tree.column(column, width=width, stretch=(column == "title"))
    tree.pack(fill="both", expand=True, padx=10, pady=(0, 6))

    controls = {}
    for row in cockpit.get("controls", []):
        control_id = row["controlId"]
        controls[control_id] = row
        tree.insert(
            "", "end", iid=control_id,
            values=(control_id, row["status"], row.get("severity"), "YES" if row.get("blocksCurrentGate") else "", row.get("title")),
        )

    detail = tk.Text(root, height=10, wrap="word", state="disabled")
    detail.pack(fill="x", padx=10, pady=(0, 6))

    def show_detail(_event=None):
        selected = tree.selection()
        if not selected:
            return
        row = controls[selected[0]]
        detail.configure(state="normal")
        detail.delete("1.0", "end")
        detail.insert("1.0", json.dumps(row, indent=2, sort_keys=True))
        detail.configure(state="disabled")

    tree.bind("<<TreeviewSelect>>", show_detail)
    ttk.Label(
        root,
        text="PASS is control/evidence scoped. N/A and NOT_VERIFIED are distinct. This view does not authorize release or claim CAPT is universally secure.",
    ).pack(fill="x", padx=10, pady=(0, 8))
    root.mainloop()


def main() -> int:
    parser = argparse.ArgumentParser(description="CAPT Security Closure Cockpit")
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    cockpit = load_cockpit(args.profile, args.evidence, args.source_sha)
    if args.headless:
        print(json.dumps(cockpit, indent=2, sort_keys=True))
    else:
        run_window(cockpit)
    return 0 if cockpit["gateDecision"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
