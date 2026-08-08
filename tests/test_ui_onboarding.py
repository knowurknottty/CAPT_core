"""Tests for the first-run onboarding flow (Phase 7)."""

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from capt_ui.operator.models import ModelManager  # noqa: E402
from capt_ui.operator.onramp import Onboarding, run_onboarding  # noqa: E402
from capt_ui.operator.providers import ProviderManager  # noqa: E402


@pytest.fixture
def ob_state(tmp_path):
    cfg = tmp_path / "ui"
    pm = ProviderManager(cfg)
    pm.update("ollama", {"models": ["qwen2.5:7b", "llama3.2"]})
    pm.activate("ollama")
    mm = ModelManager(cfg, providers=pm)
    return pm, mm


def test_onboarding_step_sequence(ob_state):
    pm, mm = ob_state
    # no live operator required for the config-only steps
    from capt_ui.operator.runtime import Operator
    from capt_ui.operator.bootstrap import resolve_runtime
    sock, token = resolve_runtime()
    if not (sock and token):
        pytest.skip("no runtime; skipping live onboarding steps")
    op = Operator(sock, token); op.connect()
    ob = Onboarding(op, pm, mm)
    steps = ob.steps()
    assert steps[0] == "welcome" and steps[-1] == "done"
    assert len(steps) == 12


def test_onboarding_welcome_choose_test(ob_state):
    pm, mm = ob_state
    from capt_ui.operator.runtime import Operator
    from capt_ui.operator.bootstrap import resolve_runtime
    sock, token = resolve_runtime()
    if not (sock and token):
        pytest.skip("no runtime")
    op = Operator(sock, token); op.connect()
    ob = Onboarding(op, pm, mm)
    r = ob.apply("welcome")
    assert r["ok"] and r["next"] == "choose_provider"
    r = ob.apply("choose_provider", provider_id="ollama")
    assert r["ok"] and r["next"] == "test"
    r = ob.apply("test", provider_id="ollama")
    assert r["next"] in ("choose_model", "test")


def test_onboarding_choose_model_sets_default(ob_state):
    pm, mm = ob_state
    ob = Onboarding(_dummy_op(), pm, mm)
    # directly exercise model selection without network
    r = ob.apply("choose_model", model_id="qwen2.5:7b", provider_id="ollama")
    assert r.get("ok")
    assert mm.active().model_id == "qwen2.5:7b"


def test_run_onboarding_trace(tmp_path):
    from capt_ui.operator.bootstrap import resolve_runtime
    sock, token = resolve_runtime()
    if not (sock and token):
        pytest.skip("no runtime for full onboarding")
    from capt_ui.operator.runtime import Operator
    op = Operator(sock, token); op.connect()
    res = run_onboarding(op, tmp_path)
    assert "trace" in res


class _dummy_op:
    connected = False
    def memory_policy(self):
        return {}
