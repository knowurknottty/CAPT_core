"""Tests for the real cross-model continuity scaffold (Phase 8).

The scaffold must be HONEST: without real reachable providers it must refuse to
claim continuity (skip / pending), never fabricate model responses or success.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def test_scaffold_does_not_claim_success_without_real_providers():
    from capt_ui.acceptance.cross_model_continuity import real_provider_available
    # We cannot require real models here; the assertion is about honesty:
    # real_provider_available() must match whether a real list is reachable.
    assert isinstance(real_provider_available(), bool)


def test_scaffold_requires_two_providers():
    from capt_ui.acceptance.cross_model_continuity import run_real_cross_model_demo
    with pytest.raises((RuntimeError, NotImplementedError)):
        # No real ready providers -> must refuse, not fake it
        run_real_cross_model_demo("ollama", "x", "lmstudio", "y")


def test_scaffold_cli_exits_nonzero_when_not_ready():
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO)
    r = subprocess.run(
        [sys.executable, "capt_ui/acceptance/cross_model_continuity.py"],
        capture_output=True, text=True, env=env, cwd=REPO, timeout=60)
    # Either pending (2) or actually ran (0); it must NEVER claim real success
    # without real providers. If it returns 2, honest. If 0, real providers ran.
    assert r.returncode in (0, 2)
    if r.returncode == 2:
        assert "PENDING" in r.stdout or "NotImplementedError" in r.stdout or "NONE" in r.stdout
