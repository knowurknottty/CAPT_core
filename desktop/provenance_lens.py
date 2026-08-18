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


def layout_provenance_graph(
    graph: Dict[str, Any], *, x_gap: int = 240, y_gap: int = 82
) -> Dict[str, Dict[str, int]]:
    """Return deterministic layered coordinates for an already-validated DAG."""
    nodes = {str(node["id"]): node for node in graph.get("nodes", [])}
    topo = [str(node_id) for node_id in graph.get("topologicalOrder", []) if str(node_id) in nodes]
    for node_id in sorted(nodes):
        if node_id not in topo:
            topo.append(node_id)

    incoming = {node_id: [] for node_id in nodes}
    for edge in graph.get("edges", []):
        source = str(edge["source"])
        target = str(edge["target"])
        if source in nodes and target in nodes:
            incoming[target].append(source)

    depth: Dict[str, int] = {}
    for node_id in topo:
        parents = incoming.get(node_id, [])
        depth[node_id] = max((depth.get(parent, 0) + 1 for parent in parents), default=0)

    layers: Dict[int, list[str]] = {}
    order_index = {node_id: index for index, node_id in enumerate(topo)}
    for node_id, value in depth.items():
        layers.setdefault(value, []).append(node_id)

    positions: Dict[str, Dict[str, int]] = {}
    for layer in sorted(layers):
        members = sorted(layers[layer], key=lambda node_id: (order_index.get(node_id, 10**9), node_id))
        for row, node_id in enumerate(members):
            positions[node_id] = {
                "x": 60 + layer * x_gap,
                "y": 50 + row * y_gap,
                "depth": layer,
            }
    return positions


def _draw_graph(canvas, graph: Dict[str, Any]) -> None:
    import tkinter as tk

    positions = layout_provenance_graph(graph)
    nodes = {str(node["id"]): node for node in graph.get("nodes", [])}
    width, height = 176, 46

    for edge in graph.get("edges", []):
        source = str(edge["source"])
        target = str(edge["target"])
        if source not in positions or target not in positions:
            continue
        left = positions[source]
        right = positions[target]
        x1, y1 = left["x"] + width, left["y"] + height // 2
        x2, y2 = right["x"], right["y"] + height // 2
        canvas.create_line(x1, y1, x2, y2, arrow=tk.LAST, width=1)
        canvas.create_text(
            (x1 + x2) // 2,
            (y1 + y2) // 2 - 8,
            text=str(edge.get("relation", "")),
            anchor="s",
            font=("TkDefaultFont", 8),
        )

    for node_id, pos in positions.items():
        node = nodes[node_id]
        x, y = pos["x"], pos["y"]
        canvas.create_rectangle(x, y, x + width, y + height, width=1)
        canvas.create_text(
            x + 8,
            y + 9,
            text=str(node.get("kind", "unknown")),
            anchor="nw",
            font=("TkDefaultFont", 9, "bold"),
        )
        canvas.create_text(
            x + 8,
            y + 27,
            text=str(node.get("identity", ""))[:26],
            anchor="nw",
            font=("TkDefaultFont", 8),
        )

    if positions:
        max_x = max(pos["x"] for pos in positions.values()) + width + 80
        max_y = max(pos["y"] for pos in positions.values()) + height + 80
    else:
        max_x, max_y = 640, 320
    canvas.configure(scrollregion=(0, 0, max_x, max_y))


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
    root.geometry("1280x780")

    header = ttk.Frame(root, padding=10)
    header.pack(fill="x")
    ttk.Label(header, text="CAPT Provenance Lens", font=("TkDefaultFont", 16, "bold")).pack(side="left")
    ttk.Label(
        header,
        text="projection only • explicit links only • missing links remain unknown",
    ).pack(side="right")

    outer = ttk.Panedwindow(root, orient="vertical")
    outer.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    graph_frame = ttk.Frame(outer)
    canvas = tk.Canvas(graph_frame, highlightthickness=0)
    x_scroll = ttk.Scrollbar(graph_frame, orient="horizontal", command=canvas.xview)
    y_scroll = ttk.Scrollbar(graph_frame, orient="vertical", command=canvas.yview)
    canvas.configure(xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set)
    canvas.grid(row=0, column=0, sticky="nsew")
    y_scroll.grid(row=0, column=1, sticky="ns")
    x_scroll.grid(row=1, column=0, sticky="ew")
    graph_frame.rowconfigure(0, weight=1)
    graph_frame.columnconfigure(0, weight=1)
    _draw_graph(canvas, graph)
    outer.add(graph_frame, weight=3)

    inspector = ttk.Frame(outer)
    tree = ttk.Treeview(inspector, columns=("kind", "identity"), show="headings", height=9)
    tree.heading("kind", text="Kind")
    tree.heading("identity", text="Identity")
    tree.column("kind", width=190, anchor="w")
    tree.column("identity", width=520, anchor="w")
    tree.pack(fill="x")

    nodes = list(graph.get("nodes", []))
    by_id = {node["id"]: node for node in nodes}
    for node in nodes:
        tree.insert("", "end", iid=node["id"], values=(node["kind"], node["identity"]))

    detail = tk.Text(inspector, wrap="word", height=12, state="disabled")
    detail.pack(fill="both", expand=True, pady=(6, 0))
    outer.add(inspector, weight=2)

    def selected(_event=None):
        chosen = tree.selection()
        if not chosen:
            return
        node_id = chosen[0]
        node = by_id[node_id]
        incoming = [e for e in graph.get("edges", []) if e["target"] == node_id]
        outgoing = [e for e in graph.get("edges", []) if e["source"] == node_id]
        body = {
            "node": node,
            "incoming": incoming,
            "outgoing": outgoing,
            "graphAuthority": graph.get("authority"),
            "graphDigest": graph.get("graphDigest"),
        }
        detail.configure(state="normal")
        detail.delete("1.0", "end")
        detail.insert("1.0", json.dumps(body, sort_keys=True, indent=2))
        detail.configure(state="disabled")

    tree.bind("<<TreeviewSelect>>", selected)
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
