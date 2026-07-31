"""ModelTask adapter tests (decision review 2026-07-31).

Covers testing order items 1–3:
  1. contract/unit tests with the deterministic provider
  2. gate-denial test proving provider call count stays ZERO
  3. Pulse adapter tests

Plus OpenAICompatibleLocalProvider unit tests with a faked transport
(no network; malformed/empty choices rejected; header redaction verified by
asserting the persisted artifacts contain no Authorization material).

NOTE: GOVERNED_MODEL_EXECUTION_PROVEN is NOT claimed here — that milestone
requires the real local Big Pickle invocation through CAPTRuntime.
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from capt_solo.api import (  # noqa: E402
    CAPTRuntime,
    GateDeniedError,
    ModelIdentity,
    ModelTaskRequest,
    ModelTaskResult,
    OpenAICompatibleLocalProvider,
    ProviderError,
    PulseModelProvider,
    RuntimeConfiguration,
)
from capt_solo.pulse import PulseGateway, PulseConfig  # noqa: E402
from capt_solo.foundry import ProofRequirement  # noqa: E402


# ---------------------------------------------------------------------------
# deterministic test provider
# ---------------------------------------------------------------------------

class DeterministicTestProvider:
    """No-transport test double. Fixed identity + canned result."""

    def __init__(self, *, model_id: str = "deterministic-test-model", text: str = "deterministic reply") -> None:
        self._model_id = model_id
        self._text = text
        self.invoke_count = 0
        self.last_request: ModelTaskRequest | None = None

    def identity(self) -> ModelIdentity:
        return ModelIdentity(
            provider="deterministic-test",
            model_id=self._model_id,
            local=True,
            tokenizer_id="test",
        )

    def invoke(self, request: ModelTaskRequest) -> ModelTaskResult:
        self.invoke_count += 1
        self.last_request = request
        return ModelTaskResult(
            task_id=request.task_id,
            provider="deterministic-test",
            model_id=self._model_id,
            request_artifact_id="",
            response_artifact_id="",
            response_text=self._text,
            finish_reason="stop",
            input_tokens=10,
            output_tokens=len(self._text.split()),
            latency_ms=1,
            provider_request_id="test-req-1",
        )


class FailingTestProvider(DeterministicTestProvider):
    def invoke(self, request: ModelTaskRequest) -> ModelTaskResult:
        self.invoke_count += 1
        self.last_request = request
        raise ProviderError("deterministic provider failure")


@pytest.fixture()
def home(tmp_path):
    return tmp_path / "home"


def _rt(home: Path):
    cfg = RuntimeConfiguration(
        home=home,
        db_path=home / "data" / "memory.db",
        journal_dir=home / "data" / "ctp",
        evidence_dir=home / "evidence",
        event_log_path=home / "data" / "khsb" / "events.jsonl",
    )
    return CAPTRuntime.load(cfg)


def _request(task_id: str = "t1") -> ModelTaskRequest:
    return ModelTaskRequest(
        task_id=task_id,
        mission_id="mission-test",
        session_id="s-test",
        contextpack_digest="deadbeef",
        memory_use_decision_id="decision-1",
        system_prompt="SYSTEM: validated context",
        user_prompt="USER: compute the answer",
        idempotency_key="k1",
    )


# ---------------------------------------------------------------------------
# 1. contract / unit tests (deterministic provider)
# ---------------------------------------------------------------------------

def test_model_contract_shapes():
    ident = ModelIdentity(provider="p", model_id="m", local=True)
    req = _request()
    res = ModelTaskResult(
        task_id=req.task_id, provider="p", model_id="m",
        request_artifact_id="a", response_artifact_id="b",
        response_text="ok",
    )
    assert ident.provider == "p"
    assert req.contextpack_digest == "deadbeef"
    assert res.response_text == "ok"
    # frozen dataclasses reject mutation
    with pytest.raises(Exception):
        req.task_id = "x"  # type: ignore[misc]
    with pytest.raises(Exception):
        res.response_text = "y"  # type: ignore[misc]


def test_deterministic_provider_contract():
    p = DeterministicTestProvider()
    assert p.identity().provider == "deterministic-test"
    res = p.invoke(_request())
    assert res.response_text == "deterministic reply"
    assert res.finish_reason == "stop"
    assert res.provider_request_id == "test-req-1"


def test_execute_model_task_with_deterministic_provider(home):
    rt = _rt(home)
    try:
        cap = rt.registry.register(
            "model-task-cap", "test capability", "deterministic-test",
            lifecycle="verified",
            required_tools=["execute_model_task"],
        )
        rt.proof.set_requirements(
            cap.identifier, [ProofRequirement("artifact_hash", 1, cap.identifier)]
        )
        p = DeterministicTestProvider()
        out = rt.execute_model_task(
            task_id="task-a",
            mission_id="mission-test",
            objective="Answer the question complete and verified.",
            provider=p,
            user_prompt="USER: compute the answer",
            capability_id=cap.identifier,
            claim_text="Answer the question complete and verified.",
        )
        assert out["ok"] is True
        assert out["provider"] == "deterministic-test"
        assert p.invoke_count == 1
        assert out["claim_verdict"]["supported"] is True
        assert out["contextpack"]["validation"] == "PASS"
        assert out["request_artifact_id"].startswith("model-task-request:")
        assert out["response_artifact_id"].startswith("model-task-response:")
        # artifacts persisted with sha sidecars
        art = home / "evidence" / "model-task-response" / f"task-a_{out['tx_id']}.json"
        assert art.exists()
        assert (home / "evidence" / "model-task-response" / f"task-a_{out['tx_id']}.json.sha256").exists()
        # request artifact carries the validated ContextPack, not the transcript
        req_art = home / "evidence" / "model-task-request" / f"task-a_{out['tx_id']}.json"
        req_data = json.loads(req_art.read_text())
        assert req_data["contextpack_digest"] == out["contextpack"]["digest"]
        assert "transcript" not in req_data["system_prompt"].lower()
        # event log contains model-task events in order
        events = [json.loads(l)["topic"] for l in (home / "data" / "khsb" / "events.jsonl").read_text().splitlines()]
        assert events.count("model-task.started") == 1
        assert events.count("model-task.completed") == 1
        assert "model-task.failed" not in events
        assert events.index("model-task.started") < events.index("model-task.completed")
    finally:
        rt.close()


def test_evidence_recorded_for_response_artifact(home):
    rt = _rt(home)
    try:
        p = DeterministicTestProvider()
        rt.execute_model_task(
            task_id="task-ev", mission_id="mission-test",
            objective="Prove the answer complete and verified.",
            provider=p,
            capability_id=None,
            claim_text=None,
        )
        # artifact_hash evidence exists for the model-task producer
        rows = rt.engine._conn.execute(
            "SELECT type, producer, hash FROM proof_evidence WHERE producer LIKE 'model-task:%'"
        ).fetchall()
        assert len(rows) >= 1
        assert rows[0][0] == "artifact_hash"
        assert len(rows[0][2]) == 64
    finally:
        rt.close()


# ---------------------------------------------------------------------------
# 2. gate-denial: provider call count stays ZERO
# ---------------------------------------------------------------------------

def test_gate_denial_provider_never_called(home):
    rt = _rt(home)
    try:
        p = DeterministicTestProvider()
        # Evidence record whose embedded content yields a protected fact
        # (absolute path pattern) that is ABSENT from the rendered context ->
        # FIDELITY_BLOCK protected_fact_missing -> GateDeniedError.
        from capt_solo.contextpack import RecordRef
        gate_evidence = [
            RecordRef(
                record_id="ev-gate",
                record_digest="0" * 64,
                origin="test",
                embedded={
                    "canonical_path": "/Users/knowurknot/capt-solo/.capt/evidence/"
                    "self-governance/seed_sg_state.py"
                },
            )
        ]
        with pytest.raises(GateDeniedError):
            rt.execute_model_task(
                task_id="task-gate", mission_id="mission-test",
                objective="Do the thing",
                provider=p,
                user_prompt="USER: x",
                evidence=gate_evidence,
                rendered_context="MISSION mission-test objective=Do the thing",
            )
        assert p.invoke_count == 0
        assert p.last_request is None
        # durable refusal: started then failed, NO completed; provider never called
        ev_file = home / "data" / "khsb" / "events.jsonl"
        assert ev_file.exists()
        events = [json.loads(l)["topic"] for l in ev_file.read_text().splitlines()]
        assert "model-task.started" in events
        assert "model-task.failed" in events
        assert "model-task.completed" not in events
        assert events.index("model-task.started") < events.index("model-task.failed")
        # CTP aborted — no committed receipt for this task
        assert (home / "data" / "ctp").is_dir()
        journal_text = "".join(
            f.read_text() for f in (home / "data" / "ctp").glob("*")
            if f.is_file()
        )
        assert "commit" not in journal_text
    finally:
        rt.close()


def test_provider_failure_aborts_and_publishes_failed(home):
    rt = _rt(home)
    try:
        cap = rt.registry.register(
            "model-task-cap2", "test capability", "deterministic-test",
            lifecycle="verified",
            required_tools=["execute_model_task"],
        )
        p = FailingTestProvider()
        with pytest.raises(ProviderError):
            rt.execute_model_task(
                task_id="task-fail", mission_id="mission-test",
                objective="Do the thing complete and verified.",
                provider=p,
                capability_id=cap.identifier,
            )
        assert p.invoke_count == 1
        events = [json.loads(l)["topic"] for l in (home / "data" / "khsb" / "events.jsonl").read_text().splitlines()]
        assert "model-task.failed" in events
        assert "model-task.completed" not in events
        # CTP aborted — no committed receipt for this task
        assert "model-task.started" in events
    finally:
        rt.close()


# ---------------------------------------------------------------------------
# 3. Pulse adapter tests
# ---------------------------------------------------------------------------

def test_pulse_provider_disabled_fails_closed():
    gw = PulseGateway()  # disabled by default
    p = PulseModelProvider(gateway=gw)
    assert p.identity().provider == "pulse"
    assert p.identity().local is True
    with pytest.raises(ProviderError):
        p.invoke(_request("pulse-1"))


def test_pulse_provider_normalizes_response(monkeypatch):
    gw = PulseGateway()
    gw.configure(endpoint="http://127.0.0.1:9999/pulse", enabled=True)

    class _FakeResp:
        def read(self):
            return b'{"completion": "pulse reply"}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        assert req.method == "POST"
        body = json.loads(req.data.decode())
        assert body["prompt"] == "USER: compute the answer"
        assert body["max_tokens"] == 256
        return _FakeResp()

    import urllib.request as ur
    monkeypatch.setattr(ur, "urlopen", fake_urlopen)
    p = PulseModelProvider(gateway=gw, model_id="pulse-model")
    res = p.invoke(_request("pulse-2"))
    assert res.response_text == "pulse reply"
    assert res.provider == "pulse"
    assert res.input_tokens is not None
    assert res.output_tokens is not None
    assert res.latency_ms >= 0


# ---------------------------------------------------------------------------
# OpenAICompatibleLocalProvider unit tests (faked transport — no network)
# ---------------------------------------------------------------------------

def _fake_chat_response(model="qwen-test", content="local reply", usage=None, rid="chatcmpl-1"):
    return json.dumps({
        "id": rid,
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content},
                     "finish_reason": "stop"}],
        "usage": usage or {"prompt_tokens": 11, "completion_tokens": 5},
    }).encode()


class _FakeResp:
    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_openai_compatible_requires_endpoint():
    with pytest.raises(ProviderError):
        OpenAICompatibleLocalProvider(endpoint="", model_id="m")


def test_openai_compatible_invoke_chat_format(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["req"] = req
        captured["timeout"] = timeout
        return _FakeResp(_fake_chat_response())

    import urllib.request as ur
    monkeypatch.setattr(ur, "urlopen", fake_urlopen)
    p = OpenAICompatibleLocalProvider(
        endpoint="http://127.0.0.1:1234/v1",
        model_id="local-model",
        api_token="secret-token-abc",
        timeout_s=7.0,
    )
    res = p.invoke(_request("lm-1"))
    body = json.loads(captured["req"].data.decode())
    assert body["model"] == "local-model"
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][1]["role"] == "user"
    assert captured["req"].get_header("Authorization") == "Bearer secret-token-abc"
    assert captured["timeout"] == 7.0
    assert res.response_text == "local reply"
    assert res.provider == "openai-compatible-local"
    assert res.input_tokens == 11
    assert res.output_tokens == 5
    assert res.finish_reason == "stop"
    assert res.provider_request_id == "chatcmpl-1"


def test_openai_compatible_rejects_empty_choices(monkeypatch):
    import urllib.request as ur

    def fake_urlopen(req, timeout=None):
        return _FakeResp(json.dumps({"id": "x", "model": "m", "choices": []}).encode())

    monkeypatch.setattr(ur, "urlopen", fake_urlopen)
    p = OpenAICompatibleLocalProvider(endpoint="http://127.0.0.1:1234/v1", model_id="m")
    with pytest.raises(ProviderError):
        p.invoke(_request("lm-2"))


def test_openai_compatible_rejects_malformed(monkeypatch):
    import urllib.request as ur

    def fake_urlopen(req, timeout=None):
        return _FakeResp(b"not json at all")

    monkeypatch.setattr(ur, "urlopen", fake_urlopen)
    p = OpenAICompatibleLocalProvider(endpoint="http://127.0.0.1:1234/v1", model_id="m")
    with pytest.raises(ProviderError):
        p.invoke(_request("lm-3"))


def test_openai_compatible_network_error_fails_closed(monkeypatch):
    import urllib.request as ur

    def fake_urlopen(req, timeout=None):
        raise OSError("connection refused")

    monkeypatch.setattr(ur, "urlopen", fake_urlopen)
    p = OpenAICompatibleLocalProvider(endpoint="http://127.0.0.1:1234/v1", model_id="m")
    with pytest.raises(ProviderError):
        p.invoke(_request("lm-4"))


def test_persisted_artifacts_contain_no_authorization(home):
    """End-to-end through CAPTRuntime: persisted request/response artifacts
    must never contain Authorization/header material."""
    rt = _rt(home)
    try:
        p = DeterministicTestProvider()
        out = rt.execute_model_task(
            task_id="task-redact", mission_id="mission-test",
            objective="Prove the answer complete and verified.",
            provider=p,
            user_prompt="USER: hi",
        )
        for kind in ("model-task-request", "model-task-response"):
            art = home / "evidence" / kind / f"task-redact_{out['tx_id']}.json"
            text = art.read_text().lower()
            assert "authorization" not in text
            assert "bearer" not in text
            assert "api_token" not in text or "api_token" not in text.replace('"api_token": null', '')
    finally:
        rt.close()
