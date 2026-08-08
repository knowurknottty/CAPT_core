"""Tests for the golden acceptance demo (Phase 8)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def test_golden_demo_runs():
    from capt_ui.operator.bootstrap import resolve_runtime
    sock, token = resolve_runtime()
    if not (sock and token):
        pytest.skip("no running CAPT runtime for golden demo")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO)
    r = subprocess.run(
        [sys.executable, "capt_ui/acceptance/golden_demo.py"],
        capture_output=True, text=True, env=env, cwd=REPO, timeout=60)
    assert r.returncode == 0, r.stderr
    for tag in ("model_a", "mission", "checkpoint", "shutdown", "model_b",
                "resume", "evidence", "claimguard", "done"):
        assert ("[%s]" % tag.upper()) in r.stdout, tag
    assert "GOLDEN DEMO SUMMARY" in r.stdout
