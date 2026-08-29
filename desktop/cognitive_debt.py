#!/usr/bin/env python3
"""Standalone concrete Cognitive Debt cockpit (CAPT-UPG-024)."""
from __future__ import annotations

import argparse
import json
from typing import Any, Dict

from capt_ui.operator.cognitive_debt import project_cognitive_debt
from desktop.desktop_runtime_client import RuntimeClient, project_authoritative_state


def load_debt(sock_path: str, token_file: str) -> Dict[str, Any]:
    client = RuntimeClient(sock_path, token_file)
    client.connect()
    try:
        state = project_authoritative_state(client)
        capabilities = []
        cohorts = []
        for aggregate in client.list_aggregates():
            kind = aggregate.get("kind")
            if kind not in ("capability", "cohort"):
                continue
            snapshot = client.get_state(aggregate["streamId"])
            if not snapshot:
                continue
            if kind == "capability":
                capabilities.append(snapshot)
            else:
                cohorts.append(snapshot)
        state["capabilities"] = capabilities
        state["cohorts"] = cohorts
        return project_cognitive_debt(state)
    finally:
        client.disconnect()


def run_window(debt: Dict[str, Any]) -> None:
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("CAPT Cognitive Debt")
    root.geometry("1150x720")

    ttk.Label(
        root,
        text="Concrete cognitive debt | items %d | blocking %d | no opaque confidence score" % (
            debt.get("itemCount", 0), debt.get("blockingItemCount", 0)
        ),
    ).pack(fill="x", padx=10, pady=8)

    columns = ("category", "blocking", "source", "reason")
    tree = ttk.Treeview(root, columns=columns, show="headings")
    for column, width in (("category", 220), ("blocking", 80), ("source", 220), ("reason", 560)):
        tree.heading(column, text=column.upper())
        tree.column(column, width=width, stretch=(column == "reason"))
    tree.pack(fill="both", expand=True, padx=10, pady=(0, 8))

    by_id = {}
    for item in debt.get("items", []):
        debt_id = item["debtId"]
        by_id[debt_id] = item
        tree.insert(
            "", "end", iid=debt_id,
            values=(
                item["category"],
                "YES" if item["blocking"] else "",
                "%s:%s" % (item["sourceType"], item["sourceId"]),
                item["reason"],
            ),
        )

    detail = tk.Text(root, height=8, wrap="word", state="disabled")
    detail.pack(fill="x", padx=10, pady=(0, 6))

    def show_detail(_event=None):
        selected = tree.selection()
        if not selected:
            return
        item = by_id[selected[0]]
        detail.configure(state="normal")
        detail.delete("1.0", "end")
        detail.insert("1.0", json.dumps(item, indent=2, sort_keys=True))
        detail.configure(state="disabled")

    tree.bind("<<TreeviewSelect>>", show_detail)
    ttk.Label(
        root,
        text="Debt is source-linked unresolved state. Absence of recorded debt is not proof of correctness, and this view cannot halt or mutate CAPT.",
    ).pack(fill="x", padx=10, pady=(0, 8))
    root.mainloop()


def main() -> int:
    parser = argparse.ArgumentParser(description="CAPT concrete cognitive debt cockpit")
    parser.add_argument("--sock", required=True)
    parser.add_argument("--token-file", required=True)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    debt = load_debt(args.sock, args.token_file)
    if args.headless:
        print(json.dumps(debt, indent=2, sort_keys=True))
    else:
        run_window(debt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
