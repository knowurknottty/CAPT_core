"""Regression: capt_cli must anchor sys.path at the repo root, not its parent.

A stray ``capt_runtime/tools`` fragment in the user's home directory shadowed
the repo package when capt_cli inserted ``Path(__file__).parent.parent``,
breaking ``capt`` from any non-repo cwd (ModuleNotFoundError for
capt_runtime.tools.backends.cloudflare_resource_inventory).
"""
from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_capt_cli_src_is_repo_root():
    tree = ast.parse((REPO / "capt_cli.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_SRC":
                    src = ast.unparse(node.value)
                    assert src == "Path(__file__).resolve().parent", src
                    return
    raise AssertionError("_SRC assignment not found in capt_cli.py")
