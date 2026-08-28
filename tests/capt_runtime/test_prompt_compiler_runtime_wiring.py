from __future__ import annotations

import json

from capt_runtime.composition import create_runtime
from capt_runtime.prompt_compiler import PromptCompileRequest


def _stage(stage: str) -> dict:
    return {
        "stage": stage,
        "outcome": "bounded outcome",
        "scope": "repository",
        "inputs": ["operator prompt"],
        "outputs": ["execution prompt"],
        "constraints": ["preserve CAPT authority"],
        "successCriteria": ["tests pass"],
        "ambiguities": [],
        "requestedCapabilities": [],
    }


class _Response:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False
    def read(self, limit: int = -1):
        if limit < 0:
            return self.payload
        return self.payload[:limit]


def _write_config(tmp_path, provider: dict, model: str):
    ui = tmp_path / "ui"
    ui.mkdir()
    (ui / "providers.json").write_text(json.dumps({"providers": [provider]}))
    (ui / "models.json").write_text(json.dumps({
        "default": {"provider": provider["id"], "model": model}
    }))
    return ui


def test_transport_uses_strict_schema_and_capability_guard(monkeypatch):
    from desktop.prompt_compiler_provider import (
        LocalPromptCompilerSelection,
        OpenAICompatiblePromptCompilerTransport,
    )

    seen = {}

    def fake_urlopen(request, timeout):
        if request.full_url.endswith("/models"):
            payload = {"data": [{"id": "qwen3.8-27b-mtplx"}]}
            return _Response(json.dumps(payload).encode("utf-8"))
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        seen["body"] = json.loads(request.data.decode("utf-8"))
        content = json.dumps(_stage("OMNI"))
        payload = {"choices": [{"message": {"content": content}}]}
        return _Response(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(
        "desktop.prompt_compiler_provider.urllib.request.urlopen", fake_urlopen
    )
    selection = LocalPromptCompilerSelection(
        "mtplx", "qwen3.8-27b-mtplx", "http://127.0.0.1:18085/v1"
    )
    transport = OpenAICompatiblePromptCompilerTransport(selection)
    result = transport({
        "stage": "OMNI",
        "allowedCapabilities": [],
        "responseSchema": {"type": "object"},
        "currentPrompt": "Implement a tested fix.",
    })

    assert result == _stage("OMNI")
    assert seen["url"] == "http://127.0.0.1:18085/v1/chat/completions"
    assert seen["body"]["stream"] is False
    assert seen["body"]["temperature"] == 0
    schema = seen["body"]["response_format"]["json_schema"]
    assert schema["strict"] is True
    assert schema["schema"]["type"] == "object"
    system = seen["body"]["messages"][0]["content"]
    assert "requestedCapabilities" in system
    assert "subset" in system.lower()
    assert "first character" in system.lower()
    assert "markdown" in system.lower()


def test_transport_rejects_non_object_model_content(monkeypatch):
    from desktop.prompt_compiler_provider import (
        LocalPromptCompilerSelection,
        OpenAICompatiblePromptCompilerTransport,
    )

    def fake_urlopen(_request, timeout):
        assert timeout > 0
        payload = {"choices": [{"message": {"content": "[]"}}]}
        return _Response(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(
        "desktop.prompt_compiler_provider.urllib.request.urlopen", fake_urlopen
    )
    transport = OpenAICompatiblePromptCompilerTransport(
        LocalPromptCompilerSelection(
            "mtplx", "qwen3.8-27b-mtplx", "http://127.0.0.1:18085/v1"
        )
    )
    import pytest
    with pytest.raises(ValueError, match="object"):
        transport({
            "stage": "OMNI", "allowedCapabilities": [],
            "responseSchema": {"type": "object"}, "currentPrompt": "x",
        })


def test_runtime_composition_injects_prompt_compiler(tmp_path):
    from capt_runtime.prompt_compiler import PromptCompiler

    runtime = create_runtime(str(tmp_path / "ledger.db"))
    compiler = PromptCompiler()
    try:
        command_service = runtime.command_service(
            "operator", "session", prompt_compiler=compiler
        )
        assert command_service.prompt_compiler is compiler
    finally:
        runtime.close()


def test_factory_refuses_remote_only_configuration(tmp_path):
    from desktop.prompt_compiler_provider import build_local_prompt_compiler

    ui = _write_config(tmp_path, {
        "id": "openrouter", "kind": "cloud", "transport": "openai_compatible",
        "base_url": "https://openrouter.ai/api/v1", "enabled": True,
    }, "remote/model")

    assert build_local_prompt_compiler(ui) is None


def test_runtime_capabilities_advertise_prompt_proposal_commands(tmp_path):
    from desktop.capt_runtime_service import RuntimeQueryService

    runtime = create_runtime(str(tmp_path / "ledger.db"))
    try:
        result = RuntimeQueryService(
            runtime.store, memory_engine=runtime.memory_engine
        ).handle({"op": "capabilities"})["result"]
        operations = set(result["commandOperations"])
        assert {
            "compile_prompt_proposal", "revise_prompt_proposal",
            "cancel_prompt_proposal", "request_prompt_proposal_approval",
        }.issubset(operations)
    finally:
        runtime.close()


def test_transport_resolves_unambiguous_local_model_alias(monkeypatch):
    from desktop.prompt_compiler_provider import (
        LocalPromptCompilerSelection,
        OpenAICompatiblePromptCompilerTransport,
    )

    seen = {}

    def fake_urlopen(request, timeout):
        assert timeout > 0
        if request.full_url.endswith("/models"):
            payload = {"data": [
                {"id": "Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed"},
                {"id": "/Users/operator/.cache/model/snapshot"},
            ]}
            return _Response(json.dumps(payload).encode("utf-8"))
        seen["body"] = json.loads(request.data.decode("utf-8"))
        content = json.dumps(_stage("OMNI"))
        payload = {"choices": [{"message": {"content": content}}]}
        return _Response(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(
        "desktop.prompt_compiler_provider.urllib.request.urlopen", fake_urlopen
    )
    transport = OpenAICompatiblePromptCompilerTransport(
        LocalPromptCompilerSelection(
            "mtplx", "qwen3.8-27b-mtplx", "http://127.0.0.1:18085/v1"
        )
    )

    transport({
        "stage": "OMNI", "allowedCapabilities": [],
        "responseSchema": {"type": "object"}, "currentPrompt": "x",
    })

    assert seen["body"]["model"] == "Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed"


def test_remote_prompt_compiler_default_timeout_is_bounded(monkeypatch):
    from desktop.prompt_compiler_provider import (
        OpenAICompatiblePromptCompilerTransport,
        PromptCompilerSelection,
    )

    seen = {}

    def fake_urlopen(request, timeout):
        seen["timeout"] = timeout
        content = json.dumps(_stage("OMNI"))
        payload = {"choices": [{"message": {"content": content}}]}
        return _Response(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(
        "desktop.prompt_compiler_provider.urllib.request.urlopen", fake_urlopen
    )
    transport = OpenAICompatiblePromptCompilerTransport(
        PromptCompilerSelection(
            "openrouter",
            "z-ai/glm-5.3-flash",
            "https://openrouter.ai/api/v1",
            "remote",
            "keychain:openrouter",
            True,
        ),
        api_key="test-key",
    )
    transport({
        "stage": "OMNI",
        "allowedCapabilities": [],
        "responseSchema": {"type": "object"},
        "currentPrompt": "stress prompt",
    })

    assert 0 < seen["timeout"] <= 20
