"""Portable Node discovery tests (mission Part 2).

These verify the resolver WITHOUT requiring Node to actually be installed:
they exercise PATH resolution, the CAPT_NODE_BIN override, genuine absence,
an invalid override, and that the resolver never executes arbitrary shell
commands. The real parity test (test_contracts) still runs when Node is
present, so parity remains real.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest import mock

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "contracts" / "tools"))

from node_discovery import discover_node_bin, require_node_bin  # noqa: E402


def test_node_found_on_path(monkeypatch):
    monkeypatch.delenv("CAPT_NODE_BIN", raising=False)
    with mock.patch("node_discovery.shutil.which", return_value="/usr/bin/node"), \
         mock.patch("node_discovery._is_executable", return_value=True):
        assert discover_node_bin() == "/usr/bin/node"


def test_node_found_through_explicit_override(monkeypatch, tmp_path):
    node = tmp_path / "node"
    node.write_bytes(b"#!/bin/sh\n")
    node.chmod(0o755)
    monkeypatch.setenv("CAPT_NODE_BIN", str(node))
    # override path is real + executable -> returned as-is
    assert discover_node_bin() == str(node)


def test_node_genuinely_absent(monkeypatch):
    monkeypatch.delenv("CAPT_NODE_BIN", raising=False)
    with mock.patch("node_discovery.shutil.which", return_value=None), \
         mock.patch("node_discovery._is_executable", return_value=False):
        assert discover_node_bin() is None


def test_invalid_override_path_rejected(monkeypatch, tmp_path):
    # Point at a file that does not exist -> override must NOT be trusted.
    monkeypatch.setenv("CAPT_NODE_BIN", str(tmp_path / "does-not-exist"))
    with mock.patch("node_discovery.shutil.which", return_value=None), \
         mock.patch("node_discovery._is_executable", return_value=False):
        assert discover_node_bin() is None


def test_parity_failure_propagates(monkeypatch):
    """A failing parity run must remain a test failure, not a silent pass."""
    monkeypatch.delenv("CAPT_NODE_BIN", raising=False)
    node = "/usr/bin/node"
    with mock.patch("node_discovery.shutil.which", return_value=node), \
         mock.patch("node_discovery._is_executable", return_value=True), \
         mock.patch("subprocess.run") as run:
        # Simulate ts_parity.mjs exiting non-zero with failure payload.
        proc = mock.Mock()
        proc.returncode = 1
        proc.stdout = '{"failures":3,"cases":[]}\n'
        proc.stderr = "FAIL x\n"
        run.return_value = proc
        import subprocess

        result = subprocess.run(
            [node, str(REPO / "contracts/tools/ts_parity.mjs")],
            cwd=REPO, capture_output=True, text=True,
        )
        assert result.returncode != 0
        assert '"failures":3' in result.stdout


def test_resolver_does_not_execute_shell_commands(monkeypatch):
    """discover_node_bin must never shell out to locate node."""
    monkeypatch.delenv("CAPT_NODE_BIN", raising=False)
    calls = []

    def fake_which(cmd):
        calls.append(cmd)
        return None

    with mock.patch("node_discovery.shutil.which", side_effect=fake_which), \
         mock.patch("node_discovery._is_executable", return_value=False), \
         mock.patch("os.path.isfile", return_value=False):
        result = discover_node_bin()
    assert result is None
    # Only shutil.which("node") may be called; no shell/exec of a locator.
    assert calls == ["node"]
