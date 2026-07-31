"""CAPT ModelTask — the ONE canonical model-execution abstraction.

ModelProvider is the single model-agnostic boundary through which model
invocations enter the governed CAPT execution path (decision review
2026-07-31). Pulse and LM Studio are SIBLING adapters; neither payload is the
universal CAPT provider contract.

Contract:
    ModelProvider
    ├── identity() -> ModelIdentity
    └── invoke(ModelTaskRequest) -> ModelTaskResult

Provider responsibilities:
- serialize request
- perform transport
- normalize response
- report model identity, latency, usage, finish reason, provider request ID
- fail closed on malformed or failed responses

Safety:
- No network import at module import time (lazy urllib, like PulseGateway).
- Disabled-by-default posture preserved (PulseModelProvider raises
  ProviderError unless explicitly configured; OpenAICompatibleLocalProvider
  requires an explicit endpoint).
- Authorization headers are NEVER returned in artifacts — the runtime
  persists only the dataclass fields (request/response bodies), never headers.
- No retry in v1. No tools in the first milestone.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Protocol, Tuple

__all__ = [
    "ModelIdentity",
    "ModelTaskRequest",
    "ModelTaskResult",
    "ModelProvider",
    "ProviderError",
    "PulseModelProvider",
    "OpenAICompatibleLocalProvider",
]


class ProviderError(Exception):
    """Raised on provider failure; the governed path fails closed."""


@dataclass(frozen=True)
class ModelIdentity:
    provider: str
    model_id: str
    model_revision: Optional[str] = None
    endpoint: Optional[str] = None
    local: bool = False
    context_limit: Optional[int] = None
    tokenizer_id: Optional[str] = None


@dataclass(frozen=True)
class ModelTaskRequest:
    task_id: str
    mission_id: str
    session_id: str
    contextpack_digest: str
    memory_use_decision_id: str
    active_directive_ids: Tuple[str, ...] = ()
    system_prompt: str = ""
    user_prompt: str = ""
    tool_definitions: Tuple[dict, ...] = ()
    response_schema: Optional[dict] = None
    max_output_tokens: Optional[int] = None
    temperature: Optional[float] = None
    idempotency_key: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelTaskResult:
    task_id: str
    provider: str
    model_id: str
    request_artifact_id: str
    response_artifact_id: str
    response_text: str
    tool_calls: Tuple[dict, ...] = ()
    finish_reason: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    latency_ms: int = 0
    provider_request_id: Optional[str] = None
    model_revision: Optional[str] = None
    evidence_ids: Tuple[str, ...] = ()


class ModelProvider(Protocol):
    """The one canonical model-execution abstraction."""

    def identity(self) -> ModelIdentity:
        ...

    def invoke(self, request: ModelTaskRequest) -> ModelTaskResult:
        ...


# ---------------------------------------------------------------------------
# token estimation (no tokenizer dependency; explicit estimate markers)
# ---------------------------------------------------------------------------

def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# PulseModelProvider — sibling adapter over the existing PulseGateway transport
# ---------------------------------------------------------------------------

class PulseModelProvider:
    """ModelProvider adapter over the existing PulseGateway transport.

    PulseGateway remains disabled-by-default and fail-closed; this adapter
    normalizes its custom payload into the canonical ModelTaskResult shape.
    Pulse's custom payload is NOT the universal CAPT provider contract — it is
    one sibling adapter.
    """

    def __init__(self, gateway: Any = None, *, model_id: Optional[str] = None) -> None:
        if gateway is None:
            from capt_solo.pulse import default_gateway

            gateway = default_gateway()
        self._gateway = gateway
        _cfg = getattr(gateway, "_config", None)
        self._model_id = model_id or (getattr(_cfg, "model", None) if _cfg else None) or "local-default"

    def identity(self) -> ModelIdentity:
        cfg = getattr(self._gateway, "_config", None)
        return ModelIdentity(
            provider="pulse",
            model_id=self._model_id,
            endpoint=getattr(cfg, "endpoint", None) if cfg else None,
            local=True,
            tokenizer_id="approx-chars/4",
        )

    def invoke(self, request: ModelTaskRequest) -> ModelTaskResult:
        from capt_solo.pulse import PulseDisabled, PulseError

        prompt = request.user_prompt or request.system_prompt
        started = time.monotonic()
        try:
            text = self._gateway.complete(
                prompt,
                max_tokens=request.max_output_tokens or 256,
            )
        except (PulseDisabled, PulseError) as exc:
            raise ProviderError(f"pulse provider failed closed: {exc}") from exc
        latency_ms = int((time.monotonic() - started) * 1000)
        return ModelTaskResult(
            task_id=request.task_id,
            provider="pulse",
            model_id=self._model_id,
            request_artifact_id="",
            response_artifact_id="",
            response_text=text,
            finish_reason=None,
            input_tokens=_estimate_tokens(prompt),
            output_tokens=_estimate_tokens(text),
            latency_ms=latency_ms,
        )


# ---------------------------------------------------------------------------
# OpenAICompatibleLocalProvider — LM Studio / local OpenAI-compatible endpoint
# ---------------------------------------------------------------------------

class OpenAICompatibleLocalProvider:
    """Minimal OpenAI-compatible chat-completions provider (LM Studio).

    - endpoint supplied explicitly; local endpoint only by default
    - chat-completions request format
    - system and user messages remain distinct
    - no transcript injection (payload carries only the request's prompts)
    - parses model, choices, finish_reason, usage, and request id where supplied
    - rejects empty or malformed choices
    - redacts authorization headers from artifacts (headers never returned)
    - no retry in v1; no tools in the first milestone
    - timeout explicit and bounded
    """

    def __init__(
        self,
        *,
        endpoint: str,
        model_id: str,
        api_token: Optional[str] = None,
        timeout_s: float = 30.0,
        local: bool = True,
        context_limit: Optional[int] = None,
    ) -> None:
        if not endpoint:
            raise ProviderError("OpenAICompatibleLocalProvider requires an explicit endpoint")
        self._endpoint = endpoint.rstrip("/")
        self._model_id = model_id
        self._api_token = api_token
        self._timeout_s = timeout_s
        self._local = local
        self._context_limit = context_limit

    def identity(self) -> ModelIdentity:
        return ModelIdentity(
            provider="openai-compatible-local",
            model_id=self._model_id,
            endpoint=self._endpoint,
            local=self._local,
            context_limit=self._context_limit,
            tokenizer_id=None,
        )

    def _chat_completions_url(self) -> str:
        if self._endpoint.endswith("/chat/completions"):
            return self._endpoint
        return self._endpoint + "/chat/completions"

    def invoke(self, request: ModelTaskRequest) -> ModelTaskResult:
        import json
        import urllib.error
        import urllib.request

        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        if request.user_prompt:
            messages.append({"role": "user", "content": request.user_prompt})
        if not messages:
            raise ProviderError("model task request carries no prompt content")
        body: dict = {
            "model": self._model_id,
            "messages": messages,
        }
        if request.max_output_tokens is not None:
            body["max_tokens"] = request.max_output_tokens
        if request.temperature is not None:
            body["temperature"] = request.temperature
        headers = {"Content-Type": "application/json"}
        if self._api_token:
            headers["Authorization"] = f"Bearer {self._api_token}"
        data = json.dumps(body).encode("utf-8")
        started = time.monotonic()
        try:
            req = urllib.request.Request(
                self._chat_completions_url(), data=data, headers=headers, method="POST"
            )
            with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:
                raw = resp.read().decode("utf-8")
        except Exception as exc:  # fail closed
            raise ProviderError(f"openai-compatible-local request failed: {exc}") from exc
        latency_ms = int((time.monotonic() - started) * 1000)
        try:
            parsed = json.loads(raw)
        except Exception as exc:
            raise ProviderError("malformed JSON response from provider") from exc
        choices = parsed.get("choices") or []
        if not choices or not isinstance(choices[0], dict):
            raise ProviderError("provider returned empty or malformed choices")
        message = choices[0].get("message") or {}
        text = message.get("content")
        if text is None:
            text = ""
        usage = parsed.get("usage") or {}
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")
        return ModelTaskResult(
            task_id=request.task_id,
            provider="openai-compatible-local",
            model_id=parsed.get("model") or self._model_id,
            request_artifact_id="",
            response_artifact_id="",
            response_text=text,
            tool_calls=(),
            finish_reason=choices[0].get("finish_reason"),
            input_tokens=input_tokens if input_tokens is not None else _estimate_tokens(
                request.system_prompt + request.user_prompt
            ),
            output_tokens=output_tokens if output_tokens is not None else _estimate_tokens(text),
            latency_ms=latency_ms,
            provider_request_id=parsed.get("id"),
            model_revision=None,
        )
