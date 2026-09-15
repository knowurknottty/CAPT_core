from __future__ import annotations

from pathlib import Path

import pytest

from capt_ui.operator.contract import ProviderKind
from capt_ui.operator.models import ModelManager
from capt_ui.operator.providers import Provider, ProviderManager


def _local(provider_id: str, *, port: int, models: list[str]) -> Provider:
    return Provider(
        id=provider_id,
        name=provider_id,
        kind=ProviderKind.LOCAL,
        transport="openai_compatible",
        base_url=f"http://127.0.0.1:{port}/v1",
        models=models,
    )


def test_failed_local_probe_preserves_last_known_model_index(tmp_path: Path) -> None:
    pm = ProviderManager(tmp_path / "ui")
    pm.add(_local("cached-local", port=1, models=["cached-model"]))

    probed = pm.test("cached-local")

    assert probed.health.value == "red"
    assert probed.models == ["cached-model"]


def test_model_default_rejects_provider_model_mismatch(tmp_path: Path) -> None:
    cfg = tmp_path / "ui"
    pm = ProviderManager(cfg)
    pm.add(_local("local-a", port=18085, models=["owned-model"]))
    mm = ModelManager(cfg, providers=pm)

    with pytest.raises(ValueError, match="not indexed"):
        mm.set_default("local-a", "remote-only-model")


def test_setting_default_model_selects_its_provider_atomically(tmp_path: Path) -> None:
    cfg = tmp_path / "ui"
    pm = ProviderManager(cfg)
    pm.add(_local("local-a", port=18085, models=["model-a"]))
    pm.add(_local("local-b", port=18086, models=["model-b"]))
    pm.activate("local-a")
    mm = ModelManager(cfg, providers=pm)

    mm.set_default("local-b", "model-b")

    reloaded = ProviderManager(cfg)
    assert reloaded.get("local-b") is not None
    assert reloaded.get("local-b").selected is True
    assert reloaded.get("local-a").selected is False
    assert ModelManager(cfg, providers=reloaded).summary()["default"] == {
        "provider": "local-b", "model": "model-b"
    }


def test_refresh_local_includes_custom_loopback_and_skips_cloud(tmp_path: Path, monkeypatch) -> None:
    cfg = tmp_path / "ui"
    pm = ProviderManager(cfg)
    pm.add(_local("custom-local", port=18085, models=["old-model"]))
    calls: list[str] = []

    def fake_test(provider_id: str, api_key: str = ""):
        calls.append(provider_id)
        return pm.get(provider_id)

    monkeypatch.setattr(pm, "test", fake_test)
    refreshed = pm.refresh_local()

    assert "custom-local" in calls
    assert "openrouter" not in calls
    assert {p.id for p in refreshed} == set(calls)


def test_cli_refresh_local_preserves_cached_index(tmp_path: Path, monkeypatch, capsys) -> None:
    from capt_ui.operator.cli import main as operator_main

    state = tmp_path / "state"
    cfg = state / "ui"
    monkeypatch.delenv("CAPT_SOLO_HOME", raising=False)
    monkeypatch.setenv("CAPT_STATE_DIR", str(state))
    pm = ProviderManager(cfg)
    pm.add(_local("cached-local", port=1, models=["cached-model"]))

    assert operator_main(["providers", "--refresh-local", "--json"]) == 0
    capsys.readouterr()

    reloaded = ProviderManager(cfg)
    assert reloaded.get("cached-local") is not None
    assert reloaded.get("cached-local").models == ["cached-model"]
