"""Local-only Prompt Intelligence compiler transport selection for desktop runtime."""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from capt_runtime.provider_endpoint import endpoint_class
from capt_runtime.resource_governor import TokenCostGovernor

_MAX_RESPONSE_BYTES = 262_144


@dataclass(frozen=True)
class LocalPromptCompilerSelection:
    provider_id: str
    model: str
    base_url: str


def _local_selection(
    providers: list[Any], provider_id: str, model: str
) -> Optional[LocalPromptCompilerSelection]:
    if not provider_id or not model:
        return None
    for provider in providers:
        if not isinstance(provider, dict) or str(provider.get("id")) != provider_id:
            continue
        base_url = str(provider.get("base_url") or "")
        if (
            provider.get("enabled", True)
            and str(provider.get("kind")) == "local"
            and str(provider.get("transport")) == "openai_compatible"
            and endpoint_class(base_url) == "local"
        ):
            return LocalPromptCompilerSelection(provider_id, model, base_url.rstrip("/"))
        return None
    return None


def select_local_prompt_compiler(ui_config_dir: Path) -> Optional[LocalPromptCompilerSelection]:
    """Resolve Prompt Intelligence independently from the execution-model default.

    Priority is an explicit ``prompt-compiler.json`` binding, then a legacy local
    execution default, then one unambiguous configured loopback compiler. A cloud
    execution default never becomes a prompt compiler and ambiguity fails closed.
    """
    ui = Path(ui_config_dir)
    try:
        providers_doc = json.loads((ui / "providers.json").read_text())
    except (OSError, ValueError, TypeError):
        return None
    providers = providers_doc.get("providers") if isinstance(providers_doc, dict) else None
    if not isinstance(providers, list):
        return None

    explicit_path = ui / "prompt-compiler.json"
    if explicit_path.exists():
        try:
            explicit = json.loads(explicit_path.read_text())
        except (OSError, ValueError, TypeError):
            return None
        if not isinstance(explicit, dict):
            return None
        return _local_selection(
            providers, str(explicit.get("provider") or ""), str(explicit.get("model") or "")
        )

    try:
        models_doc = json.loads((ui / "models.json").read_text())
    except (OSError, ValueError, TypeError):
        models_doc = {}
    default = models_doc.get("default") if isinstance(models_doc, dict) else None
    if isinstance(default, dict):
        legacy = _local_selection(
            providers, str(default.get("provider") or ""), str(default.get("model") or "")
        )
        if legacy is not None:
            return legacy

    candidates: list[LocalPromptCompilerSelection] = []
    for provider in providers:
        if not isinstance(provider, dict):
            continue
        provider_id = str(provider.get("id") or "")
        models = provider.get("models")
        if not isinstance(models, list):
            continue
        model_ids = [str(item) for item in models if isinstance(item, str) and item.strip()]
        if not model_ids:
            continue
        preferred = next((item for item in model_ids if not item.startswith("/")), model_ids[0])
        selection = _local_selection(providers, provider_id, preferred)
        if selection is not None:
            candidates.append(selection)
    return candidates[0] if len(candidates) == 1 else None


class OpenAICompatiblePromptCompilerTransport:
    """Bounded JSON-schema transport for a verified loopback compiler endpoint."""

    def __init__(self, selection: LocalPromptCompilerSelection, *, timeout_seconds: int = 120):
        if endpoint_class(selection.base_url) != "local":
            raise ValueError("prompt compiler transport requires a loopback endpoint")
        self.selection = selection
        self.timeout_seconds = int(timeout_seconds)
        self._resolved_model: Optional[str] = None

    @staticmethod
    def _normalized_model_id(value: str) -> str:
        return "".join(ch.lower() for ch in value if ch.isalnum())

    def _request_model(self) -> str:
        if self._resolved_model is not None:
            return self._resolved_model
        request = urllib.request.Request(
            self.selection.base_url + "/models",
            headers={"Accept": "application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=min(self.timeout_seconds, 5)) as response:
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except OSError:
            return self.selection.model
        if len(raw) > _MAX_RESPONSE_BYTES:
            raise ValueError("prompt compiler model discovery exceeded byte limit")
        try:
            envelope = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError, TypeError):
            return self.selection.model
        data = envelope.get("data") if isinstance(envelope, dict) else None
        if not isinstance(data, list):
            return self.selection.model
        advertised = [
            str(item.get("id")) for item in data
            if isinstance(item, dict) and isinstance(item.get("id"), str) and item.get("id")
        ]
        if self.selection.model in advertised:
            self._resolved_model = self.selection.model
            return self._resolved_model
        needle = self._normalized_model_id(self.selection.model)
        matches = [
            model_id for model_id in advertised
            if not model_id.startswith("/")
            and needle
            and needle in self._normalized_model_id(model_id)
        ]
        if len(matches) == 1:
            self._resolved_model = matches[0]
            return self._resolved_model
        if len(matches) > 1:
            raise ValueError("prompt compiler model alias matched multiple advertised models")
        raise ValueError("configured prompt compiler model is not advertised by local endpoint")

    def __call__(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        response_schema = payload.get("responseSchema")
        if not isinstance(response_schema, Mapping):
            raise ValueError("prompt compiler response schema is required")
        system = (
            "You are CAPT Prompt Intelligence operating analysis-only. Output exactly one JSON object "
            "matching the supplied schema. The first character of the response MUST be { and the final "
            "character MUST be }. Do not use Markdown or code fences and do not include commentary before "
            "or after the JSON object. Never claim execution, verification, promotion, or completion. "
            "requestedCapabilities MUST be a subset of allowedCapabilities; when allowedCapabilities "
            "is empty, requestedCapabilities MUST be an empty array."
        )
        body = {
            "model": self._request_model(),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(dict(payload), sort_keys=True)},
            ],
            "stream": False,
            "temperature": 0,
            "max_tokens": 4096,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "capt_prompt_stage",
                    "strict": True,
                    "schema": dict(response_schema),
                },
            },
        }
        request = urllib.request.Request(
            self.selection.base_url + "/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
        if len(raw) > _MAX_RESPONSE_BYTES:
            raise ValueError("prompt compiler response exceeded byte limit")
        envelope = json.loads(raw.decode("utf-8"))
        choices = envelope.get("choices") if isinstance(envelope, dict) else None
        content = (choices or [{}])[0].get("message", {}).get("content") if isinstance(choices, list) else None
        if not isinstance(content, str) or not content.strip():
            raise ValueError("prompt compiler returned no structured content")
        result = json.loads(content)
        if not isinstance(result, dict):
            raise ValueError("prompt compiler stage output must be an object")
        return result


def build_local_prompt_compiler(ui_config_dir: Path):
    """Construct a bounded local compiler or return None; never falls back to remote."""
    selection = select_local_prompt_compiler(Path(ui_config_dir))
    if selection is None:
        return None
    from capt_runtime.prompt_compiler import (
        BoundedPromptCompilerRunner, CompilerProvider, PromptCompiler,
    )
    governor = TokenCostGovernor(
        max_tokens_per_session=131_072,
        max_cost_usd_per_session=0.01,
        max_requests_per_session=32,
        max_output_tokens_per_request=4096,
    )
    return PromptCompiler(
        runner=BoundedPromptCompilerRunner(
            OpenAICompatiblePromptCompilerTransport(selection), governor=governor
        ),
        provider=CompilerProvider(selection.provider_id, selection.model, "local"),
    )
