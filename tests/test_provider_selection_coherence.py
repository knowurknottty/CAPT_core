from __future__ import annotations

from pathlib import Path

from capt_ui.operator.cli import main as operator_main
from capt_ui.operator.contract import ProviderKind
from capt_ui.operator.models import ModelManager
from capt_ui.operator.providers import Provider, ProviderManager


def _seed_mtplx(config_dir: Path) -> None:
    pm = ProviderManager(config_dir)
    pm.add(
        Provider(
            id="mtplx",
            name="Qwen3.8-27B MTPLX (Local MLX)",
            kind=ProviderKind.LOCAL,
            transport="openai_compatible",
            base_url="http://127.0.0.1:18085/v1",
            context_limit=262144,
            models=["qwen3.8-27b-mtplx"],
        )
    )


def test_provider_activation_updates_global_model_tuple(tmp_path: Path, monkeypatch) -> None:
    state_dir = tmp_path / "state"
    config_dir = state_dir / "ui"
    monkeypatch.delenv("CAPT_SOLO_HOME", raising=False)
    monkeypatch.setenv("CAPT_STATE_DIR", str(state_dir))
    _seed_mtplx(config_dir)

    pm = ProviderManager(config_dir)
    pm.activate("ollama")
    ModelManager(config_dir, providers=pm).set_default(
        "ollama", "qwen3.8-27b-mtplx"
    )

    assert operator_main([
        "providers", "--activate", "mtplx", "--json"
    ]) == 0

    providers = ProviderManager(config_dir)
    models = ModelManager(config_dir, providers=providers)
    assert providers.get("mtplx").selected is True
    assert models.summary()["default"] == {
        "provider": "mtplx",
        "model": "qwen3.8-27b-mtplx",
    }


def test_legacy_provider_registry_backfills_current_defaults(tmp_path: Path) -> None:
    config_dir = tmp_path / "ui"
    config_dir.mkdir(parents=True)
    (config_dir / "providers.json").write_text(
        '{"providers":[{"id":"ollama","name":"Ollama","kind":"local",'
        '"transport":"ollama","base_url":"http://localhost:11434/v1",'
        '"context_limit":8192,"enabled":true,"selected":true,'
        '"models":["legacy-model"],"capabilities":["chat"]}]}'
    )

    pm = ProviderManager(config_dir)
    assert pm.get("ollama").models == ["legacy-model"]
    assert pm.get("openrouter") is not None
    assert pm.get("lmstudio") is not None


def test_unconfigured_legacy_native_mlx_placeholder_is_retired(tmp_path: Path) -> None:
    config_dir = tmp_path / "ui"
    pm = ProviderManager(config_dir)
    assert pm.get("mlx") is None
