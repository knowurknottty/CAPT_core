"""Tests for the CAPT operator CLI surface (shared layer CLI)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _run(*args, env):
    e = dict(os.environ)
    e.update(env)
    return subprocess.run(
        [sys.executable, "-m", "capt_ui.operator.cli", *args],
        capture_output=True, text=True, env=e, cwd=REPO)


def _runtime_env():
    from capt_ui.operator.bootstrap import resolve_runtime
    sock, token = resolve_runtime()
    if not (sock and token):
        return None
    return {"PYTHONPATH": str(REPO)}


def test_cli_status_against_runtime():
    env = _runtime_env()
    if not env:
        pytest.skip("no running runtime")
    r = _run("status", env=env)
    assert r.returncode == 0, r.stderr
    assert "runtime:" in r.stdout


def test_cli_providers_list():
    env = {"PYTHONPATH": str(REPO)}
    r = _run("providers", "--json", env=env)
    assert r.returncode == 0
    import json
    rows = json.loads(r.stdout)
    assert any(p["id"] == "ollama" for p in rows)


def test_cli_verbosity_roundtrip():
    env = {"PYTHONPATH": str(REPO), "CAPT_SOLO_HOME": "/tmp/capt-cli-vtest-%d" % __import__("time").time()}
    r = _run("verbosity", "--set", "diagnostic", env=env)
    assert r.returncode == 0
    r2 = _run("verbosity", env=env)
    assert "diagnostic" in r2.stdout


def test_cli_memory_store_real():
    import uuid
    env = _runtime_env()
    if not env:
        pytest.skip("no running runtime for memory store CLI test")
    content = "cli memory probe %s" % uuid.uuid4().hex[:6]
    r = _run("memory", "--store", content, env=env)
    assert r.returncode == 0, r.stderr
    assert '"ok": true' in r.stdout or "ok:" in r.stdout
