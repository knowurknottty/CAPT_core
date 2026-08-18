#!/usr/bin/env python3
"""Standalone desktop Provenance Lens for CAPT (CAPT-UPG-017).

The window consumes only authenticated runtime read projections and the shared
provenance DAG builder. It never mutates CAPT state.
"""
from __future__ import annotations

import argparse
import json
from typing import Any, Dict

from capt_ui.operator.provenance import build_provenance_graph
from desktop.desktop_runtime_client import RuntimeClient, project_authoritative_state


def load_graph(sock_path: str, token_file: str) -> Dict[str, Any]:
    client = RuntimeClient(sock_path, token_file)
    client.connect()
    try:
        state = project_authoritative_state(client)
        return build_provenance_graph(state)
    finally:
        client.disconnect()


def run_window(graph: Dict[str, Any]) -> None:
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("CAPT Provenance Lens")
    root.geometry("1100x700")

    header = ttk.Label(
        root,
        text="CAPT Provenance Lens — projection only | %d nodes | %d edges" % (
            len(graph.get("nodes", [])), len(graph.get("edges", []))
        ),
    )
    header.pack(fill="x", padx=10, pady=8)

    pane = ttk.Panedwindow(root, orient="horizontal")
    pane.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    left = ttk.Frame(pane)
    right = ttk.Frame(pane)
    pane.add(left, weight=2)
    pane.add(right, weight=3)

    tree = ttk.Treeview(left, columns=("kind", "identity"), show="headings")
    tree.heading("kind", text="Kind")
    tree.heading("identity", text="Identity")
    tree.column("kind", width=150, stretch=False)
    tree.column("identity", width=360, stretch=True)
    tree.pack(fill="both", expand=True)

    node_by_id = {}
    for node in graph.get("nodes", []):
        node_by_id[node["id"]] = node
        tree.insert("", "end", iid=node["id"], values=(node.get("kind"), node.get("identity")))

    detail = tk.Text(right, wrap="word", state="disabled")
    detail.pack(fill="both", expand=True)

    def show_node(_event=None):
        selected = tree.selection()
        if not selected:
            return
        node_id = selected[0]
        node = node_by_id[node_id]
        incoming = [e for e in graph.get("edges", []) if e.get("target") == node_id]
        outgoing = [e for e in graph.get("edges", []) if e.get("source") == node_id]
        payload = {
            "node": node,
            "incoming": incoming,
            "outgoing": outgoing,
            "authority": graph.get("authority"),
            "graphDigest": graph.get("graphDigest"),
        }
        detail.configure(state="normal")
        detail.delete("1.0", "end")
        detail.insert("1.0", json.dumps(payload, indent=2, sort_keys=True))
        detail.configure(state="disabled")

    tree.bind("<<TreeviewSelect>>", show_node)

    footer = ttk.Label(
        root,
        text="Missing relationships remain absent. Verification and claim decisions are separate nodes.",
    )
    footer.pack(fill="x", padx=10, pady=(0, 8))
    root.mainloop()


def main() -> int:
    parser = argparse.ArgumentParser(description="CAPT desktop provenance lens")
    parser.add_argument("--sock", required=True)
    parser.add_argument("--token-file", required=True)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    graph = load_graph(args.sock, args.token_file)
    if args.headless:
        print(json.dumps(graph, sort_keys=True, indent=2))
    else:
        run_window(graph)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
