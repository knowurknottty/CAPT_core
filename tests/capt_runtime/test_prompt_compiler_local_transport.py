from __future__ import annotations

import json


def _write_ui_config(tmp_path, providers, model_state):
    ui = tmp_path / "ui"
    ui.mkdir()
    (ui / "providers.json").write_text(json.dumps({"providers": providers}))
    (ui / "models.json").write_text(json.dumps(model_state))
    return ui


def test_local_compiler_selection_prefers_configured_default_loopback(tmp_path):
    from desktop.prompt_compiler_provider import select_local_prompt_compiler

    ui = _write_ui_config(tmp_path, [
        {"id": "openrouter", "kind": "cloud", "transport": "openai_compatible",
         "base_url": "https://openrouter.ai/api/v1", "enabled": True,
         "selected": False, "models": ["remote/model"]},
        {"id": "mtplx", "kind": "local", "transport": "openai_compatible",
         "base_url": "http://127.0.0.1:18085/v1", "enabled": True,
         "selected": True, "models": ["qwen3.8-27b-mtplx"]},
    ], {"default": {"provider": "mtplx", "model": "qwen3.8-27b-mtplx"}})

    selected = select_local_prompt_compiler(ui)

    assert selected.provider_id == "mtplx"
    assert selected.model == "qwen3.8-27b-mtplx"
    assert selected.base_url == "http://127.0.0.1:18085/v1"
