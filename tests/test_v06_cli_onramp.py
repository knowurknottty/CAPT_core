"""CAPT v0.6 P0 — CLI on-ramp tests.

Exercises the normal-human default lifecycle surface added for onboarding:

    capt memory store <text>
    capt doctor
    capt start / capt status / capt stop  (default state dir)
    capt evidence

All commands run through the actual CLI entry point (capt_cli.main) using
public interfaces only. The runtime lifecycle uses a per-test state directory
so tests are isolated and deterministic.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import pytest

from capt_runtime.cli_ramp import default_paths, is_running


@pytest.fixture
def state_dir():
    # Use a SHORT path (system temp) — Unix-domain sockets cap the path length
    # (~108 chars). pytest's default tmp_path under /private/var/folders is far
    # too long and the runtime socket bind fails with AF_UNIX path too long.
    d = Path(tempfile.gettempdir()) / ("capt-p0-" + uuid.uuid4().hex[:8])
    d.mkdir(parents=True, exist_ok=True)
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _run(*args, state_dir=None, env_extra=None):
    env = dict(os.environ)
    if state_dir is not None:
        env["CAPT_STATE_DIR"] = str(state_dir)
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, "capt_cli.py", *args],
        capture_output=True, text=True, env=env, cwd=os.getcwd())
    return proc


@pytest.fixture
def cli_home(tmp_path, monkeypatch):
    monkeypatch.setenv("CAPT_SOLO_HOME", str(tmp_path))
    return tmp_path


def test_memory_store_and_search(cli_home):
    p = _run("--json", "memory", "store", "onboarding test fact",
             "--namespace", "quickstart", "--tag", "p0")
    assert p.returncode == 0, p.stderr
    out = json.loads(p.stdout)
    assert out["namespace"] == "quickstart"

    s = _run("--json", "memory", "search", "onboarding test")
    assert s.returncode == 0
    data = json.loads(s.stdout)
    assert any(r["memory_id"] == out["memory_id"] for r in data)


def test_doctor_first_class(cli_home, state_dir):
    p = _run("doctor", state_dir=state_dir)
    assert p.returncode in (0, 1)
    assert "CAPT doctor" in p.stdout
    assert "env.package" in p.stdout


def test_start_status_evidence_stop_lifecycle(cli_home, state_dir):
    # start with a seeded demo mission
    p = _run("start", "--seed", state_dir=state_dir)
    assert p.returncode == 0, p.stderr
    assert "HEALTHY" in p.stdout

    # status
    s = _run("status", state_dir=state_dir)
    assert s.returncode == 0, s.stderr
    assert "HEALTHY" in s.stdout

    # evidence (seeded demo mission should be inspectable)
    ev = _run("--json", "evidence", state_dir=state_dir)
    assert ev.returncode == 0, ev.stderr
    evd = json.loads(ev.stdout)
    assert "verification" in evd
    assert evd["verification"]["status"]["kind"] in ("verified", "not_tested")

    # checkpoint (deterministic idempotency key)
    cp = _run("--json", "checkpoint", "--idempotency-key", "p0-cp", state_dir=state_dir)
    assert cp.returncode == 0, cp.stderr
    cpd = json.loads(cp.stdout)
    assert cpd["status"] == "accepted"

    # resume
    rs = _run("--json", "resume", "--idempotency-key", "p0-rs", state_dir=state_dir)
    assert rs.returncode == 0, rs.stderr
    assert json.loads(rs.stdout)["status"] == "accepted"

    # restore deterministic stop
    st = _run("stop", state_dir=state_dir)
    assert st.returncode == 0, st.stderr
    # give the service a moment to exit and drop the socket
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and _running(state_dir):
        time.sleep(0.1)
    # after stop, status should report not running
    s2 = _run("status", state_dir=state_dir)
    assert s2.returncode != 0
    assert "not running" in s2.stderr


def _running(state_dir):
    paths = default_paths()
    if str(paths["state_dir"]) != str(state_dir):
        # rebuild paths from the override dir
        base = state_dir
        return (base / "runtime.sock").exists() and is_running(base / "runtime.sock")
    return is_running(paths["sock"])
