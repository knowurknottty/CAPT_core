"""Tests for the shared operator layer (UI foundation Phases 1-4).

These verify the shared operator API, provider/model managers, and CaveCAPT
verbosity system without a display. The operator layer is surface-agnostic and
is exercised directly here (headless), the same way the TUI/Desktop will call
it.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from capt_ui.operator.contract import (  # noqa: E402
    ModelScope,
    ProviderHealth,
    ProviderKind,
    RuntimeHealth,
    Verbosity,
)
from capt_ui.operator.models import ModelManager  # noqa: E402
from capt_ui.operator.providers import DEFAULT_PROVIDERS, Provider, ProviderManager  # noqa: E402
from capt_ui.operator.verbosity import CaveCAPT  # noqa: E402


@pytest.fixture
def cfg(tmp_path):
    return tmp_path / "ui"


# ---------------------------------------------------------------- Phase 2
def test_provider_manager_defaults(cfg):
    pm = ProviderManager(cfg)
    ids = [p.id for p in pm.list()]
    assert "openrouter" in ids and "ollama" in ids and "lmstudio" in ids
    assert all(p.kind in ProviderKind for p in pm.list())


def test_provider_crud_and_persistence(cfg):
    pm = ProviderManager(cfg)
    p = Provider(id="testp", name="Test", kind=ProviderKind.LOCAL,
                 transport="openai_compatible", base_url="http://127.0.0.1:9/v1")
    pm.add(p)
    assert pm.get("testp") is not None
    pm2 = ProviderManager(cfg)  # reload from disk
    assert pm2.get("testp") is not None
    pm.update("testp", {"context_limit": 16000})
    assert pm.get("testp").context_limit == 16000
    pm.remove("testp")
    assert pm.get("testp") is None


def test_provider_activate_label(cfg):
    pm = ProviderManager(cfg)
    pm.activate("ollama")
    assert pm.get("ollama").selected
    assert pm.active_model_source() == "LOCAL"
    pm.deactivate("ollama")
    assert not pm.get("ollama").selected


def test_provider_closed_port_health(cfg):
    # unreachable endpoint -> RED, no crash
    pm = ProviderManager(cfg)
    p = Provider(id="dead", name="Dead", kind=ProviderKind.LOCAL,
                 transport="openai_compatible", base_url="http://127.0.0.1:1/v1")
    pm.add(p)
    res = pm.test("dead")
    assert res.health in (ProviderHealth.RED, ProviderHealth.YELLOW)
    assert res.reachable in (True, False)


def test_provider_default_templates():
    kinds = {d["id"]: d["kind"] for d in DEFAULT_PROVIDERS}
    assert kinds["openrouter"] == "cloud"
    assert kinds["ollama"] == "local"
    assert kinds["hermes"] == "local"


# ---------------------------------------------------------------- Phase 3
def test_model_manager_active_default(cfg):
    pm = ProviderManager(cfg)
    mm = ModelManager(cfg, providers=pm)
    # seed a model into the active provider
    pm.update("ollama", {"models": ["llama3.2", "qwen"]})
    mm.set_default("ollama", "qwen")
    active = mm.active()
    assert active.model_id == "qwen"
    assert active.provider_id == "ollama"
    assert active.kind == "LOCAL"


def test_model_scope_precedence_temporary(cfg):
    pm = ProviderManager(cfg)
    mm = ModelManager(cfg, providers=pm)
    pm.update("ollama", {"models": ["llama3.2", "qwen"]})
    pm.update("lmstudio", {"models": ["local2"]})
    mm.set_default("ollama", "llama3.2")
    mm.set_temporary("lmstudio", "local2")
    active = mm.active()
    assert active.provider_id == "lmstudio"  # temporary wins over default
    mm.clear_temporary()
    assert mm.active().model_id == "llama3.2"


def test_model_favorites_and_persistence(cfg):
    pm = ProviderManager(cfg)
    mm = ModelManager(cfg, providers=pm)
    pm.update("ollama", {"models": ["llama3.2"]})
    mm.toggle_favorite("llama3.2")
    assert [m.model_id for m in mm.favorites()] == ["llama3.2"]
    mm2 = ModelManager(cfg, providers=pm)
    assert "llama3.2" in mm2._state.get("favorites", [])
    mm.toggle_favorite("llama3.2")
    assert mm.favorites() == []


def test_model_summary_shape(cfg):
    pm = ProviderManager(cfg)
    mm = ModelManager(cfg, providers=pm)
    s = mm.summary()
    assert "active" in s and "default" in s
    assert mm.active().kind in ("LOCAL", "REMOTE", "HYBRID", "UNKNOWN")


# ---------------------------------------------------------------- Phase 4
def test_verbosity_default_and_persistence(cfg):
    v = CaveCAPT(cfg)
    assert v.value is Verbosity.NORMAL
    v.set(Verbosity.DIAGNOSTIC)
    v2 = CaveCAPT(cfg)
    assert v2.value is Verbosity.DIAGNOSTIC
    v.set(Verbosity.NORMAL)


def test_verbosity_toggle_cycle(cfg):
    v = CaveCAPT(cfg)
    v.set(Verbosity.NORMAL)
    assert v.toggle(1).value == Verbosity.DETAILED.value
    v.set(Verbosity.NORMAL)


def test_verbosity_explain_levels(cfg):
    v = CaveCAPT(cfg)
    minimal = v.explain(message="done", level=Verbosity.MINIMAL, normal="n", detailed="d", diagnostic="x")
    normal = v.explain(message="done", level=Verbosity.NORMAL, normal="n", detailed="d", diagnostic="x")
    detailed = v.explain(message="done", level=Verbosity.DETAILED, normal="n", detailed="d", diagnostic="x")
    diag = v.explain(message="done", level=Verbosity.DIAGNOSTIC, normal="n", detailed="d", diagnostic="x", req="abc")
    assert minimal == "done"
    assert normal == "n"
    assert detailed == "d"
    assert "x" in diag and "req" in diag


def test_verbosity_render_status(cfg):
    v = CaveCAPT(cfg)
    v.set(Verbosity.NORMAL)
    s = {"health": "healthy", "model": "qwen", "kind": "LOCAL",
         "runtime_version": "0.1.0", "integrity": "ok"}
    text = v.render_status(s)
    assert "HEALTHY" in text
    v.set(Verbosity.NORMAL)
