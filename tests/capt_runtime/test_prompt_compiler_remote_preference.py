from __future__ import annotations

import json


def _providers():
    return {
        "providers": [
            {
                "id": "openrouter",
                "kind": "cloud",
                "transport": "openai_compatible",
                "base_url": "https://openrouter.ai/api/v1",
                "enabled": True,
                "key_ref": "keychain:openrouter",
                "models": ["z-ai/glm-5.3-flash", "tencent/hy3"],
            },
            {
                "id": "mtplx",
                "kind": "local",
                "transport": "openai_compatible",
                "base_url": "http://127.0.0.1:18085/v1",
                "enabled": True,
                "key_ref": "",
                "models": ["Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed"],
            },
        ]
    }


def _write_ui(tmp_path):
    ui = tmp_path / "ui"
    ui.mkdir()
    (ui / "providers.json").write_text(json.dumps(_providers()))
    (ui / "models.json").write_text(json.dumps({
        "default": {"provider": "openrouter", "model": "tencent/hy3"}
    }))
    (ui / "prompt-compiler.json").write_text(json.dumps({
        "preferences": [
            {"provider": "openrouter", "model": "z-ai/glm-5.3-flash"},
            {"provider": "mtplx", "model": "Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed"},
        ],
        "remoteCompilationAuthorized": True,
    }))
    return ui


def test_prompt_compiler_prefers_configured_openrouter_glm_over_local(tmp_path):
    from desktop.prompt_compiler_provider import select_prompt_compiler

    selected = select_prompt_compiler(_write_ui(tmp_path))

    assert selected.provider_id == "openrouter"
    assert selected.model == "z-ai/glm-5.3-flash"
    assert selected.endpoint_class == "remote"
    assert selected.remote_authorized is True


def test_openrouter_prompt_transport_uses_bearer_key_without_model_discovery(monkeypatch, tmp_path):
    from desktop.prompt_compiler_provider import build_prompt_compiler

    ui = _write_ui(tmp_path)
    seen = {}

    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self, _limit=-1):
            stage = {
                "stage": "OMNI", "outcome": "enhanced", "scope": "prompt",
                "inputs": ["operator prompt"], "outputs": ["execution prompt"],
                "constraints": [], "successCriteria": ["clear"], "ambiguities": [],
                "requestedCapabilities": [],
            }
            return json.dumps({"choices": [{"message": {"content": json.dumps(stage)}}]}).encode()

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["headers"] = dict(request.header_items())
        seen["body"] = json.loads(request.data.decode())
        return Response()

    monkeypatch.setattr("desktop.prompt_compiler_provider.resolve_secret", lambda *_args, **_kwargs: "secret-test-key")
    monkeypatch.setattr("desktop.prompt_compiler_provider.urllib.request.urlopen", fake_urlopen)

    compiler = build_prompt_compiler(ui)
    assert compiler is not None
    from capt_runtime.prompt_compiler import PromptCompileRequest
    proposal = compiler.compile(PromptCompileRequest(
        original_prompt="Make this prompt sharper.",
        requested_engine="OMNI",
        execution_provider="openrouter",
        execution_model="tencent/hy3",
        remote_compilation_authorized=True,
    ))

    assert proposal.status == "ready_for_approval"
    assert seen["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert seen["headers"]["Authorization"] == "Bearer secret-test-key"
    assert seen["body"]["model"] == "z-ai/glm-5.3-flash"


def test_configured_remote_preference_is_persisted_compilation_authorization(monkeypatch, tmp_path):
    from desktop.prompt_compiler_provider import build_prompt_compiler
    from capt_runtime.prompt_compiler import PromptCompileRequest

    ui = _write_ui(tmp_path)

    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self, _limit=-1):
            stage = {
                "stage": "OMNI", "outcome": "enhanced", "scope": "prompt",
                "inputs": [], "outputs": ["execution prompt"], "constraints": [],
                "successCriteria": ["clear"], "ambiguities": [], "requestedCapabilities": [],
            }
            return json.dumps({"choices": [{"message": {"content": json.dumps(stage)}}]}).encode()

    monkeypatch.setattr("desktop.prompt_compiler_provider.resolve_secret", lambda *_a, **_k: "secret-test-key")
    monkeypatch.setattr("desktop.prompt_compiler_provider.urllib.request.urlopen", lambda *_a, **_k: Response())
    compiler = build_prompt_compiler(ui)
    proposal = compiler.compile(PromptCompileRequest(
        original_prompt="Enhance this.", requested_engine="OMNI",
        execution_provider="openrouter", execution_model="tencent/hy3",
        remote_compilation_authorized=False,
    ))
    assert proposal.status == "ready_for_approval"
    assert proposal.stage_records[0].provider_id == "openrouter"
    assert proposal.stage_records[0].model == "z-ai/glm-5.3-flash"
