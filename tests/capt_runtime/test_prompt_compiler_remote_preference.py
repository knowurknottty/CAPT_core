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


def test_configured_remote_preference_does_not_override_request_authority(monkeypatch, tmp_path):
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
    assert proposal.stage_records[0].provider_id == "mtplx"
    assert proposal.stage_records[0].model == "Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed"


def test_remote_glm_malformed_stage_falls_back_to_configured_local_compiler(monkeypatch, tmp_path):
    from desktop.prompt_compiler_provider import build_prompt_compiler
    from capt_runtime.prompt_compiler import PromptCompileRequest

    ui = _write_ui(tmp_path)
    calls = []

    class Response:
        def __init__(self, payload): self.payload = payload
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self, _limit=-1): return json.dumps(self.payload).encode()

    valid_stage = {
        "stage": "OMNI", "outcome": "enhanced", "scope": "prompt",
        "inputs": ["operator prompt"], "outputs": ["fallback execution prompt"],
        "constraints": [], "successCriteria": ["clear"], "ambiguities": [],
        "requestedCapabilities": [],
    }

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        if request.full_url.startswith("https://openrouter.ai/"):
            return Response({"choices": [{"message": {"content": '{"stage":"OMNI"'}}]})
        if request.full_url.endswith("/models"):
            return Response({"data": [{"id": "Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed"}]})
        return Response({"choices": [{"message": {"content": json.dumps(valid_stage)}}]})

    monkeypatch.setattr("desktop.prompt_compiler_provider.resolve_secret", lambda *_a, **_k: "secret-test-key")
    monkeypatch.setattr("desktop.prompt_compiler_provider.urllib.request.urlopen", fake_urlopen)

    compiler = build_prompt_compiler(ui)
    proposal = compiler.compile(PromptCompileRequest(
        original_prompt="Enhance this robustly.", requested_engine="OMNI",
        execution_provider="openrouter", execution_model="xiaomi/mimo-v2.5",
        remote_compilation_authorized=True,
    ))

    assert proposal.status == "ready_for_approval"
    assert proposal.stage_records[0].provider_id == "mtplx"
    assert proposal.stage_records[0].model == "Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed"
    assert calls[0] == "https://openrouter.ai/api/v1/chat/completions"
    assert "http://127.0.0.1:18085/v1/chat/completions" in calls


def test_without_compiler_override_pi_uses_selected_execution_provider_model(monkeypatch, tmp_path):
    from desktop.prompt_compiler_provider import build_prompt_compiler
    from capt_runtime.prompt_compiler import PromptCompileRequest

    ui = tmp_path / "ui"
    ui.mkdir()
    providers = _providers()
    providers["providers"] = [providers["providers"][0]]
    (ui / "providers.json").write_text(json.dumps(providers))
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
        seen["body"] = json.loads(request.data.decode())
        return Response()

    monkeypatch.setattr("desktop.prompt_compiler_provider.resolve_secret", lambda *_a, **_k: "synthetic-key")
    monkeypatch.setattr("desktop.prompt_compiler_provider.urllib.request.urlopen", fake_urlopen)

    compiler = build_prompt_compiler(ui)
    proposal = compiler.compile(PromptCompileRequest(
        original_prompt="Sharpen this prompt.",
        requested_engine="OMNI",
        execution_provider="openrouter",
        execution_model="z-ai/glm-5.3-flash",
        reasoning_effort="high",
        remote_compilation_authorized=True,
    ))

    assert proposal.status == "ready_for_approval"
    assert proposal.stage_records[0].provider_id == "openrouter"
    assert proposal.stage_records[0].model == "z-ai/glm-5.3-flash"
    assert seen["body"]["model"] == "z-ai/glm-5.3-flash"
    assert seen["body"]["reasoning"] == {"effort": "high"}


def test_unreachable_single_local_compiler_degrades_to_original_proposal(monkeypatch, tmp_path):
    from urllib.error import URLError
    from desktop.prompt_compiler_provider import build_prompt_compiler
    from capt_runtime.prompt_compiler import PromptCompileRequest

    ui = tmp_path / "ui"
    ui.mkdir()
    providers = _providers()
    providers["providers"] = [providers["providers"][1]]
    (ui / "providers.json").write_text(json.dumps(providers))
    (ui / "models.json").write_text(json.dumps({"default": {"provider": "mtplx", "model": "Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed"}}))

    monkeypatch.setattr(
        "desktop.prompt_compiler_provider.urllib.request.urlopen",
        lambda *_a, **_k: (_ for _ in ()).throw(URLError("connection refused")),
    )

    compiler = build_prompt_compiler(ui)
    proposal = compiler.compile(PromptCompileRequest(
        original_prompt="Preserve this literal prompt.", requested_engine="OMNI",
        execution_provider="openrouter", execution_model="google/gemini-3.8-flash",
    ))

    assert proposal.status == "compiler_unavailable"
    assert proposal.proposed_prompt == "Preserve this literal prompt."
    assert proposal.stage_records
    assert all(record.execution_enabled is False for record in proposal.stage_records)


def test_unreachable_local_preference_fails_over_before_chat_dispatch(monkeypatch, tmp_path):
    from urllib.error import URLError
    from desktop.prompt_compiler_provider import build_prompt_compiler
    from capt_runtime.prompt_compiler import PromptCompileRequest

    ui = tmp_path / "ui"
    ui.mkdir()
    providers = {
        "providers": [
            {"id": "dead", "kind": "local", "transport": "openai_compatible", "base_url": "http://127.0.0.1:18085/v1", "enabled": True, "models": ["dead-model"]},
            {"id": "live", "kind": "local", "transport": "openai_compatible", "base_url": "http://127.0.0.1:18086/v1", "enabled": True, "models": ["live-model"]},
        ]
    }
    (ui / "providers.json").write_text(json.dumps(providers))
    (ui / "prompt-compiler.json").write_text(json.dumps({"preferences": [
        {"provider": "dead", "model": "dead-model"},
        {"provider": "live", "model": "live-model"},
    ]}))
    calls = []

    class Response:
        def __init__(self, payload): self.payload = payload
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self, _limit=-1): return json.dumps(self.payload).encode()

    stage = {"stage": "OMNI", "outcome": "enhanced", "scope": "prompt", "inputs": [], "outputs": ["x"], "constraints": [], "successCriteria": ["clear"], "ambiguities": [], "requestedCapabilities": []}

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        if request.full_url == "http://127.0.0.1:18085/v1/models":
            raise URLError("connection refused")
        if request.full_url == "http://127.0.0.1:18086/v1/models":
            return Response({"data": [{"id": "live-model"}]})
        if request.full_url == "http://127.0.0.1:18086/v1/chat/completions":
            return Response({"choices": [{"message": {"content": json.dumps(stage)}}]})
        raise AssertionError(request.full_url)

    monkeypatch.setattr("desktop.prompt_compiler_provider.urllib.request.urlopen", fake_urlopen)
    compiler = build_prompt_compiler(ui)
    proposal = compiler.compile(PromptCompileRequest(original_prompt="Enhance safely.", requested_engine="OMNI"))

    assert proposal.status == "ready_for_approval"
    assert proposal.stage_records[0].provider_id == "live"
    assert "http://127.0.0.1:18085/v1/chat/completions" not in calls


def test_request_bound_model_mismatch_returns_safe_diagnostic_without_dispatch(tmp_path):
    from desktop.prompt_compiler_provider import build_prompt_compiler
    from capt_runtime.prompt_compiler import PromptCompileRequest

    ui = tmp_path / "ui"
    ui.mkdir()
    (ui / "providers.json").write_text(json.dumps(_providers()))
    compiler = build_prompt_compiler(ui)
    proposal = compiler.compile(PromptCompileRequest(
        original_prompt="Enhance this.", requested_engine="OMNI",
        execution_provider="openrouter", execution_model="not/in/provider-list",
        remote_compilation_authorized=True,
    ))
    assert proposal.status == "compiler_unavailable"
    assert proposal.unresolved_questions == (
        "Prompt compiler unavailable [model_not_configured_for_provider].",
    )


def test_request_bound_transport_failure_returns_safe_diagnostic(monkeypatch, tmp_path):
    from urllib.error import URLError
    from desktop.prompt_compiler_provider import build_prompt_compiler
    from capt_runtime.prompt_compiler import PromptCompileRequest

    ui = tmp_path / "ui"
    ui.mkdir()
    providers = _providers()
    providers["providers"] = [providers["providers"][1]]
    (ui / "providers.json").write_text(json.dumps(providers))
    monkeypatch.setattr(
        "desktop.prompt_compiler_provider.urllib.request.urlopen",
        lambda *_a, **_k: (_ for _ in ()).throw(URLError("private transport detail")),
    )
    proposal = build_prompt_compiler(ui).compile(PromptCompileRequest(
        original_prompt="Enhance locally.", requested_engine="OMNI",
        execution_provider="mtplx",
        execution_model="Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed",
    ))
    assert proposal.status == "compiler_unavailable"
    assert proposal.unresolved_questions == (
        "Prompt compiler unavailable [transport_unavailable].",
    )
    assert "private transport detail" not in " ".join(proposal.unresolved_questions)


def test_declared_remote_chain_rechecks_request_authority_for_every_hop(monkeypatch, tmp_path):
    from desktop.prompt_compiler_provider import build_prompt_compiler
    from capt_runtime.prompt_compiler import PromptCompileRequest

    ui = tmp_path / "ui"
    ui.mkdir()
    providers = {"providers": [
        {"id": "remote-a", "kind": "cloud", "transport": "openai_compatible",
         "base_url": "https://a.example/v1", "enabled": True,
         "key_ref": "keychain:a", "models": ["a-model"]},
        {"id": "remote-b", "kind": "cloud", "transport": "openai_compatible",
         "base_url": "https://b.example/v1", "enabled": True,
         "key_ref": "keychain:b", "models": ["b-model"]},
        {"id": "local-c", "kind": "local", "transport": "openai_compatible",
         "base_url": "http://127.0.0.1:18087/v1", "enabled": True,
         "models": ["c-model"]},
    ]}
    (ui / "providers.json").write_text(json.dumps(providers))
    (ui / "prompt-compiler.json").write_text(json.dumps({
        "remoteCompilationAuthorized": True,
        "preferences": [
            {"provider": "remote-a", "model": "a-model"},
            {"provider": "remote-b", "model": "b-model"},
            {"provider": "local-c", "model": "c-model"},
        ],
    }))
    calls = []

    class Response:
        def __init__(self, payload): self.payload = payload
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self, _limit=-1): return json.dumps(self.payload).encode()

    stage = {
        "stage": "OMNI", "outcome": "local fallback", "scope": "prompt",
        "inputs": [], "outputs": ["bounded"], "constraints": [],
        "successCriteria": ["clear"], "ambiguities": [], "requestedCapabilities": [],
    }
    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        if request.full_url.endswith("/models"):
            return Response({"data": [{"id": "c-model"}]})
        return Response({"choices": [{"message": {"content": json.dumps(stage)}}]})

    monkeypatch.setattr("desktop.prompt_compiler_provider.resolve_secret", lambda *_a, **_k: "key")
    monkeypatch.setattr("desktop.prompt_compiler_provider.urllib.request.urlopen", fake_urlopen)

    proposal = build_prompt_compiler(ui).compile(PromptCompileRequest(
        original_prompt="Enhance.", requested_engine="OMNI",
        remote_compilation_authorized=False,
    ))
    assert proposal.status == "ready_for_approval"
    assert proposal.stage_records[0].provider_id == "local-c"
    assert all(not url.startswith("https://") for url in calls)


def test_declared_remote_only_chain_without_live_authority_degrades_truthfully(tmp_path):
    from desktop.prompt_compiler_provider import build_prompt_compiler
    from capt_runtime.prompt_compiler import PromptCompileRequest

    ui = tmp_path / "ui"
    ui.mkdir()
    providers = {"providers": [
        {"id": "remote-a", "kind": "cloud", "transport": "openai_compatible",
         "base_url": "https://a.example/v1", "enabled": True,
         "key_ref": "keychain:a", "models": ["a-model"]},
        {"id": "remote-b", "kind": "cloud", "transport": "openai_compatible",
         "base_url": "https://b.example/v1", "enabled": True,
         "key_ref": "keychain:b", "models": ["b-model"]},
    ]}
    (ui / "providers.json").write_text(json.dumps(providers))
    (ui / "prompt-compiler.json").write_text(json.dumps({
        "remoteCompilationAuthorized": True,
        "preferences": [
            {"provider": "remote-a", "model": "a-model"},
            {"provider": "remote-b", "model": "b-model"},
        ],
    }))
    proposal = build_prompt_compiler(ui).compile(PromptCompileRequest(
        original_prompt="Enhance.", requested_engine="OMNI",
        remote_compilation_authorized=False,
    ))
    assert proposal.status == "compiler_unavailable"
    assert proposal.unresolved_questions == (
        "Prompt compiler unavailable [remote_not_authorized].",
    )


def test_request_bound_remote_provider_requires_live_authority_before_network(monkeypatch, tmp_path):
    import pytest
    from capt_runtime.errors import AuthorityViolation
    from capt_runtime.prompt_compiler import PromptCompileRequest
    from desktop.prompt_compiler_provider import build_prompt_compiler

    ui = tmp_path / "ui"
    ui.mkdir()
    (ui / "providers.json").write_text(json.dumps(_providers()))
    calls = []
    def forbidden_network(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("network must not be touched before remote PI authority")

    monkeypatch.setattr("desktop.prompt_compiler_provider.urllib.request.urlopen", forbidden_network)
    compiler = build_prompt_compiler(ui)
    with pytest.raises(AuthorityViolation, match="REMOTE_COMPILATION_NOT_AUTHORIZED"):
        compiler.compile(PromptCompileRequest(
            original_prompt="Enhance.", requested_engine="OMNI",
            execution_provider="openrouter", execution_model="tencent/hy3",
            remote_compilation_authorized=False,
        ))
    assert calls == []
