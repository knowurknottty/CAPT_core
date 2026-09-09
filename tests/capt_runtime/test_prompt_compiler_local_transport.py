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


def test_remote_execution_default_does_not_disable_unique_local_compiler(tmp_path):
    from desktop.prompt_compiler_provider import select_local_prompt_compiler

    ui = _write_ui_config(tmp_path, [
        {"id": "openrouter", "kind": "cloud", "transport": "openai_compatible",
         "base_url": "https://openrouter.ai/api/v1", "enabled": True,
         "selected": True, "models": ["z-ai/glm-5.3-flash"]},
        {"id": "mtplx", "kind": "local", "transport": "openai_compatible",
         "base_url": "http://127.0.0.1:18085/v1", "enabled": True,
         "selected": False, "models": ["qwen3.8-27b-mtplx"]},
    ], {"default": {"provider": "openrouter", "model": "z-ai/glm-5.3-flash"}})

    selected = select_local_prompt_compiler(ui)

    assert selected is not None
    assert selected.provider_id == "mtplx"
    assert selected.model == "qwen3.8-27b-mtplx"


def test_explicit_prompt_compiler_config_disambiguates_local_compilers(tmp_path):
    from desktop.prompt_compiler_provider import select_local_prompt_compiler

    ui = _write_ui_config(tmp_path, [
        {"id": "local-a", "kind": "local", "transport": "openai_compatible",
         "base_url": "http://127.0.0.1:18081/v1", "enabled": True,
         "selected": False, "models": ["model-a"]},
        {"id": "local-b", "kind": "local", "transport": "openai_compatible",
         "base_url": "http://127.0.0.1:18082/v1", "enabled": True,
         "selected": False, "models": ["model-b"]},
        {"id": "openrouter", "kind": "cloud", "transport": "openai_compatible",
         "base_url": "https://openrouter.ai/api/v1", "enabled": True,
         "selected": True, "models": ["z-ai/glm-5.3-flash"]},
    ], {"default": {"provider": "openrouter", "model": "z-ai/glm-5.3-flash"}})
    (ui / "prompt-compiler.json").write_text(json.dumps({
        "provider": "local-b", "model": "model-b"
    }))

    selected = select_local_prompt_compiler(ui)

    assert selected is not None
    assert selected.provider_id == "local-b"
    assert selected.model == "model-b"


def test_ambiguous_local_compilers_fail_closed_without_explicit_config(tmp_path):
    from desktop.prompt_compiler_provider import select_local_prompt_compiler

    ui = _write_ui_config(tmp_path, [
        {"id": "local-a", "kind": "local", "transport": "openai_compatible",
         "base_url": "http://127.0.0.1:18081/v1", "enabled": True,
         "selected": False, "models": ["model-a"]},
        {"id": "local-b", "kind": "local", "transport": "openai_compatible",
         "base_url": "http://127.0.0.1:18082/v1", "enabled": True,
         "selected": False, "models": ["model-b"]},
        {"id": "openrouter", "kind": "cloud", "transport": "openai_compatible",
         "base_url": "https://openrouter.ai/api/v1", "enabled": True,
         "selected": True, "models": ["z-ai/glm-5.3-flash"]},
    ], {"default": {"provider": "openrouter", "model": "z-ai/glm-5.3-flash"}})

    assert select_local_prompt_compiler(ui) is None
