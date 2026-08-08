"""Tests for the UI continuity workflow demo (Phase 8).

The demo exercises operator-surface continuity (provider/model selection,
mission, checkpoint, resume, evidence) against a live runtime. It does NOT
assert real cross-model continuity — that is a separate acceptance proof.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def test_ui_continuity_demo_runs():
    from capt_ui.operator.bootstrap import resolve_runtime
    sock, token = resolve_runtime()
    if not (sock and token):
        pytest.skip("no running CAPT runtime for UI continuity demo")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO)
    r = subprocess.run(
        [sys.executable, "capt_ui/acceptance/ui_continuity_demo.py"],
        capture_output=True, text=True, env=env, cwd=REPO, timeout=60)
    assert r.returncode == 0, r.stderr
    for tag in ("model_a", "mission", "checkpoint", "shutdown", "model_b",
                "resume", "evidence", "claimguard", "done", "memory"):
        assert ("[%s]" % tag.upper()) in r.stdout, tag
    assert "UI CONTINUITY DEMO SUMMARY" in r.stdout


def test_classification_not_cross_model():
    """The demo docstring must NOT claim cross-model continuity proof."""
    text = (Path(REPO) / "capt_ui" / "acceptance" / "ui_continuity_demo.py").read_text()
    assert "NOT a cross-model continuity proof" in text
    assert "synthetic model" in text.lower() or "SYNTHETIC model" in text
    assert "real model execution" in text
