"""CAPT-UPG-018 desktop Cohort Deliberation Chamber.

The window is projection/control only. It reads authoritative Cohort state via
Operator.cohort_chamber() and submits steering through the existing governed
Operator.steer_deliberation() command.
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, Optional, Sequence

from capt_ui.operator.runtime import Operator


def render_headless(view: Dict[str, Any]) -> str:
    return json.dumps(view, sort_keys=True, separators=(",", ":"))


def load_chamber(sock: str, token_file: str, cohort_id: str) -> Dict[str, Any]:
    op = Operator(sock, token_file)
    op.connect()
    try:
        return op.cohort_chamber(cohort_id)
    finally:
        op.disconnect()


def run_window(sock: str, token_file: str, cohort_id: str) -> None:
    import tkinter as tk
    from tkinter import messagebox, ttk

    op = Operator(sock, token_file)
    op.connect()

    root = tk.Tk()
    root.title("CAPT Cohort Deliberation Chamber")
    root.geometry("1280x820")

    header = ttk.Frame(root, padding=10)
    header.pack(fill="x")
    title = ttk.Label(header, text="CAPT Cohort Deliberation Chamber", font=("TkDefaultFont", 16, "bold"))
    title.pack(side="left")
    ttk.Label(
        header,
        text="projection only • persisted contribution metadata only • steering is governed",
    ).pack(side="right")

    status_var = tk.StringVar(value="Loading…")
    debt_var = tk.StringVar(value="")
    warnings_var = tk.StringVar(value="")
    ttk.Label(root, textvariable=status_var, padding=(10, 2)).pack(fill="x")
    ttk.Label(root, textvariable=debt_var, padding=(10, 2)).pack(fill="x")
    ttk.Label(root, textvariable=warnings_var, padding=(10, 2)).pack(fill="x")

    panes = ttk.Panedwindow(root, orient="vertical")
    panes.pack(fill="both", expand=True, padx=10, pady=6)

    contrib_frame = ttk.Frame(panes)
    columns = ("epoch", "round", "participant", "outcome", "cursor", "temporal", "material", "escalation")
    contrib = ttk.Treeview(contrib_frame, columns=columns, show="headings")
    widths = {"epoch": 60, "round": 60, "participant": 140, "outcome": 150, "cursor": 80, "temporal": 190, "material": 80, "escalation": 170}
    for name in columns:
        contrib.heading(name, text=name.replace("_", " ").title())
        contrib.column(name, width=widths[name], anchor="w")
    scroll = ttk.Scrollbar(contrib_frame, orient="vertical", command=contrib.yview)
    contrib.configure(yscrollcommand=scroll.set)
    contrib.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    panes.add(contrib_frame, weight=3)

    detail = tk.Text(panes, wrap="word", height=13, state="disabled")
    panes.add(detail, weight=2)

    steer = ttk.LabelFrame(root, text="Governed operator steering", padding=8)
    steer.pack(fill="x", padx=10, pady=(0, 10))
    directive = ttk.Entry(steer)
    directive.insert(0, "")
    directive.pack(fill="x", pady=(0, 4))
    reason = ttk.Entry(steer)
    reason.insert(0, "operator steering")
    reason.pack(fill="x", pady=(0, 4))

    current_view: Dict[str, Any] = {}

    def refresh() -> None:
        nonlocal current_view
        current_view = op.cohort_chamber(cohort_id)
        status_var.set(
            "cohort=%s  mission=%s  task=%s  epoch=%s  round=%s/%s  recorded=%s  projected=%s"
            % (
                current_view.get("cohortId"), current_view.get("missionId"), current_view.get("taskId"),
                current_view.get("currentEpoch"), current_view.get("currentRound"), current_view.get("roundCap"),
                current_view.get("recordedStoppingReason"), current_view.get("projectedStoppingReason"),
            )
        )
        debt_var.set(
            "required PASS: %s | missing: %s | debt: %s"
            % (
                ", ".join(current_view.get("requiredPassParticipants") or []) or "<none>",
                ", ".join(current_view.get("missingRequiredPassParticipants") or []) or "<none>",
                current_view.get("cognitiveDebt"),
            )
        )
        warnings_var.set(
            "warnings: %s" % (", ".join(current_view.get("integrityWarnings") or []) or "<none>")
        )
        for item in contrib.get_children():
            contrib.delete(item)
        for row in current_view.get("contributions") or []:
            contrib.insert(
                "", "end", iid=row["contributionId"],
                values=(row["epoch"], row["round"], row["participant"], row["outcome"], row["cursor"], row["temporalClass"], row["material"], row["escalation"]),
            )
        detail.configure(state="normal")
        detail.delete("1.0", "end")
        detail.insert(
            "1.0",
            json.dumps(
                {
                    "participants": current_view.get("participants"),
                    "evidenceIds": current_view.get("evidenceIds"),
                    "latestSteer": current_view.get("latestSteer"),
                    "semantics": current_view.get("semantics"),
                    "authority": current_view.get("authority"),
                },
                sort_keys=True,
                indent=2,
            ),
        )
        detail.configure(state="disabled")

    def submit_steer() -> None:
        text = directive.get().strip()
        why = reason.get().strip()
        if not text or not why:
            messagebox.showwarning("CAPT steering", "Directive and reason are required.")
            return
        receipt = op.steer_deliberation(cohort_id, text, reason=why)
        if receipt.get("status") not in ("accepted", "idempotent"):
            messagebox.showerror("CAPT steering rejected", str(receipt.get("detail") or receipt.get("error") or receipt))
            return
        directive.delete(0, "end")
        refresh()

    buttons = ttk.Frame(steer)
    buttons.pack(fill="x")
    ttk.Button(buttons, text="Submit governed steer", command=submit_steer).pack(side="left")
    ttk.Button(buttons, text="Refresh", command=refresh).pack(side="right")

    def close() -> None:
        try:
            op.disconnect()
        finally:
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    refresh()
    root.mainloop()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CAPT Cohort Deliberation Chamber")
    parser.add_argument("--sock", default=os.environ.get("CAPT_RUNTIME_SOCK", ""))
    parser.add_argument("--token-file", default=os.environ.get("CAPT_RUNTIME_TOKEN_FILE", ""))
    parser.add_argument("--cohort-id", required=True)
    parser.add_argument("--headless", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    if not args.sock or not args.token_file:
        raise SystemExit("--sock and --token-file (or CAPT_RUNTIME_* env vars) are required")
    if args.headless:
        print(render_headless(load_chamber(args.sock, args.token_file, args.cohort_id)))
        return 0
    run_window(args.sock, args.token_file, args.cohort_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
