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
        remote_compilation_authorized=False,
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


def test_openrouter_strict_schema_has_required_every_property():
    from capt_runtime.prompt_compiler.stages import stage_response_schema

    schema = stage_response_schema()
    assert set(schema["properties"]) == set(schema["required"])
    assert schema["additionalProperties"] is False
    assert "requestedCapabilities" in schema["required"]
    # Local stage decoder still owns the 32-element admission bound.
    assert "maxItems" not in schema["properties"]["requestedCapabilities"]


def test_all_compilers_fail_with_safe_persistable_failure_codes(monkeypatch, tmp_path):
    import io
    from urllib.error import HTTPError, URLError
    from desktop.prompt_compiler_provider import build_prompt_compiler
    from capt_runtime.prompt_compiler import PromptCompileRequest

    ui = _write_ui(tmp_path)
    calls = []

    def failing_urlopen(request, timeout):
        calls.append(request.full_url)
        if request.full_url.startswith("https://openrouter.ai/"):
            raise HTTPError(request.full_url, 400,
                            "SECRET-REFLECTED-ERROR-BODY", None,
                            io.BytesIO(b"sensitive response"))
        raise URLError("SECRET-REFLECTED-LOCAL-ERROR")

    monkeypatch.setattr("desktop.prompt_compiler_provider.resolve_secret",
                        lambda *_a, **_k: "secret-test-key")
    monkeypatch.setattr("desktop.prompt_compiler_provider.urllib.request.urlopen",
                        failing_urlopen)
    compiler = build_prompt_compiler(ui)
    proposal = compiler.compile(PromptCompileRequest(
        original_prompt="Review this governed mission with evidence.",
        requested_engine="OMNI",
        execution_provider="openrouter", execution_model="xiaomi/mimo-v2.6-flash",
        remote_compilation_authorized=True,
    ))

    assert proposal.status == "compiler_unavailable"
    assert proposal.proposed_prompt == proposal.original_prompt
    assert "openrouter: HTTP_400" in proposal.rationale
    assert "mtplx: TRANSPORT_UNAVAILABLE" in proposal.rationale
    assert "SECRET" not in proposal.rationale
    assert "sensitive" not in proposal.rationale
    assert any("openrouter" in url for url in calls)
    assert all(not record.execution_enabled for record in proposal.stage_records)


def test_usable_compiler_configuration_error_is_visible(monkeypatch, tmp_path):
    from desktop.prompt_compiler_provider import build_prompt_compiler
    from capt_runtime.prompt_compiler import PromptCompileRequest

    ui = _write_ui(tmp_path)
    providers = _providers()
    providers["providers"] = [providers["providers"][0]]
    (ui / "providers.json").write_text(json.dumps(providers))
    monkeypatch.setattr("desktop.prompt_compiler_provider.resolve_secret",
                        lambda *_a, **_k: "")
    compiler = build_prompt_compiler(ui)
    proposal = compiler.compile(PromptCompileRequest(
        original_prompt="Review the mission scope and evidence.",
        requested_engine="OMNI",
    ))
    assert proposal.status == "compiler_unavailable"
    assert "No compatible configured compiler" in proposal.rationale


def test_two_stage_pipeline_runs_with_strict_schema_in_mock_transport(monkeypatch, tmp_path):
    from desktop.prompt_compiler_provider import build_prompt_compiler
    from capt_runtime.prompt_compiler import PromptCompileRequest

    ui = _write_ui(tmp_path)
    captured = []
    class Response:
        def __init__(self, obj): self.obj = obj
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self, _=-1): return json.dumps(self.obj).encode()

    def fake_urlopen(request, timeout):
        body = json.loads(request.data.decode())
        wire = body["response_format"]["json_schema"]["schema"]
        assert set(wire["required"]) == set(wire["properties"])
        stage_input = json.loads(body["messages"][1]["content"])
        stage = stage_input["stage"]
        captured.append(stage)
        response = {
            "stage": stage,
            "outcome": "Review mission requirements and preserve provenance",
            "scope": "local repository, no write authority",
            "inputs": ["operator prompt"],
            "outputs": ["task-scoped review plan"],
            "constraints": ["No speculative completion"],
            "successCriteria": ["Evidence-backed issue coverage"],
            "ambiguities": [],
            "requestedCapabilities": [],
        }
        return Response({"choices": [{"message": {"content": json.dumps(response)}}]})

    monkeypatch.setattr("desktop.prompt_compiler_provider.resolve_secret",
                        lambda *_a, **_k: "dummy-key")
    monkeypatch.setattr("desktop.prompt_compiler_provider.urllib.request.urlopen",
                        fake_urlopen)
    compiler = build_prompt_compiler(ui)
    proposal = compiler.compile(PromptCompileRequest(
        original_prompt="Review the existing mission evidence and dependencies.",
        requested_engine="AUTO",
        execution_provider="openrouter",
        execution_model="xiaomi/mimo-v2.6-flash",
        remote_compilation_authorized=True,
    ))
    assert captured == ["OMNI", "META"]
    assert proposal.status == "ready_for_approval"
    assert all(record.execution_enabled for record in proposal.stage_records)
    assert proposal.proposed_prompt != proposal.original_prompt
    assert proposal.verification_contract.acceptance_criteria == (
        "Evidence-backed issue coverage",)
