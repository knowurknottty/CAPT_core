"""Prompt Intelligence compiler transport selection for desktop runtime.

Prompt enhancement and chat execution are independent axes. A configured remote
compiler may enhance a prompt before a different provider/model executes it.
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from capt_runtime.errors import AuthorityViolation
from capt_runtime.provider_endpoint import endpoint_class
from capt_runtime.resource_governor import TokenCostGovernor
from capt_ui.operator.secrets import resolve as resolve_secret

_MAX_RESPONSE_BYTES = 262_144


@dataclass(frozen=True)
class PromptCompilerSelection:
    provider_id: str
    model: str
    base_url: str
    endpoint_class: str = "local"
    key_ref: str = ""
    remote_authorized: bool = False


# Backward-compatible name used by the existing local transport tests.
LocalPromptCompilerSelection = PromptCompilerSelection


def _load_providers(ui: Path) -> list[Any]:
    try:
        doc = json.loads((ui / "providers.json").read_text())
    except (OSError, ValueError, TypeError):
        return []
    providers = doc.get("providers") if isinstance(doc, dict) else None
    return providers if isinstance(providers, list) else []


def _selection(
    providers: list[Any], provider_id: str, model: str, *, remote_authorized: bool = False
) -> Optional[PromptCompilerSelection]:
    if not provider_id or not model:
        return None
    for provider in providers:
        if not isinstance(provider, dict) or str(provider.get("id")) != provider_id:
            continue
        if not provider.get("enabled", True) or str(provider.get("transport")) != "openai_compatible":
            return None
        base_url = str(provider.get("base_url") or "").rstrip("/")
        eclass = endpoint_class(base_url)
        kind = str(provider.get("kind") or "")
        models = provider.get("models")
        if isinstance(models, list) and models and model not in [str(item) for item in models]:
            return None
        if kind == "local" and eclass == "local":
            return PromptCompilerSelection(provider_id, model, base_url, "local", str(provider.get("key_ref") or ""), False)
        if kind == "cloud" and eclass == "cloud" and remote_authorized:
            return PromptCompilerSelection(provider_id, model, base_url, "remote", str(provider.get("key_ref") or ""), True)
        return None
    return None


def _local_fallback(ui: Path, providers: list[Any]) -> Optional[PromptCompilerSelection]:
    try:
        models_doc = json.loads((ui / "models.json").read_text())
    except (OSError, ValueError, TypeError):
        models_doc = {}
    default = models_doc.get("default") if isinstance(models_doc, dict) else None
    if isinstance(default, dict):
        legacy = _selection(
            providers, str(default.get("provider") or ""), str(default.get("model") or "")
        )
        if legacy is not None and legacy.endpoint_class == "local":
            return legacy

    candidates: list[PromptCompilerSelection] = []
    for provider in providers:
        if not isinstance(provider, dict) or str(provider.get("kind")) != "local":
            continue
        models = provider.get("models")
        if not isinstance(models, list):
            continue
        model_ids = [str(item) for item in models if isinstance(item, str) and item.strip()]
        if not model_ids:
            continue
        preferred = next((item for item in model_ids if not item.startswith("/")), model_ids[0])
        candidate = _selection(providers, str(provider.get("id") or ""), preferred)
        if candidate is not None:
            candidates.append(candidate)
    return candidates[0] if len(candidates) == 1 else None


def select_local_prompt_compiler(ui_config_dir: Path) -> Optional[PromptCompilerSelection]:
    """Resolve only a local loopback Prompt Intelligence compiler."""
    ui = Path(ui_config_dir)
    providers = _load_providers(ui)
    if not providers:
        return None
    explicit_path = ui / "prompt-compiler.json"
    if explicit_path.exists():
        try:
            explicit = json.loads(explicit_path.read_text())
        except (OSError, ValueError, TypeError):
            return None
        if not isinstance(explicit, dict):
            return None
        prefs = explicit.get("preferences")
        if isinstance(prefs, list):
            for pref in prefs:
                if not isinstance(pref, dict):
                    continue
                candidate = _selection(
                    providers, str(pref.get("provider") or ""), str(pref.get("model") or "")
                )
                if candidate is not None and candidate.endpoint_class == "local":
                    return candidate
            return None
        candidate = _selection(
            providers, str(explicit.get("provider") or ""), str(explicit.get("model") or "")
        )
        return candidate if candidate is not None and candidate.endpoint_class == "local" else None
    return _local_fallback(ui, providers)


def select_prompt_compiler_preferences(ui_config_dir: Path) -> list[PromptCompilerSelection]:
    """Resolve all configured Prompt Intelligence preferences in declared order."""
    ui = Path(ui_config_dir)
    providers = _load_providers(ui)
    if not providers:
        return []
    explicit_path = ui / "prompt-compiler.json"
    if explicit_path.exists():
        try:
            explicit = json.loads(explicit_path.read_text())
        except (OSError, ValueError, TypeError):
            return []
        if not isinstance(explicit, dict):
            return []
        remote_authorized = bool(explicit.get("remoteCompilationAuthorized", False))
        prefs = explicit.get("preferences")
        if isinstance(prefs, list):
            resolved: list[PromptCompilerSelection] = []
            seen: set[tuple[str, str, str]] = set()
            for pref in prefs:
                if not isinstance(pref, dict):
                    continue
                candidate = _selection(
                    providers,
                    str(pref.get("provider") or ""),
                    str(pref.get("model") or ""),
                    remote_authorized=remote_authorized,
                )
                if candidate is None:
                    continue
                key = (candidate.provider_id, candidate.model, candidate.base_url)
                if key not in seen:
                    resolved.append(candidate)
                    seen.add(key)
            if resolved:
                return resolved
        else:
            candidate = _selection(
                providers,
                str(explicit.get("provider") or ""),
                str(explicit.get("model") or ""),
                remote_authorized=remote_authorized,
            )
            if candidate is not None:
                return [candidate]
    fallback = _local_fallback(ui, providers)
    return [fallback] if fallback is not None else []


def select_prompt_compiler(ui_config_dir: Path) -> Optional[PromptCompilerSelection]:
    """Resolve the first configured Prompt Intelligence preference."""
    preferences = select_prompt_compiler_preferences(ui_config_dir)
    return preferences[0] if preferences else None


class OpenAICompatiblePromptCompilerTransport:
    """Bounded JSON-schema transport for local or explicitly authorized remote compiler."""

    def __init__(
        self,
        selection: PromptCompilerSelection,
        *,
        api_key: str = "",
        timeout_seconds: int = 120,
    ):
        actual = endpoint_class(selection.base_url)
        if selection.endpoint_class == "local" and actual != "local":
            raise ValueError("local prompt compiler transport requires a loopback endpoint")
        if selection.endpoint_class == "remote" and actual != "cloud":
            raise ValueError("remote prompt compiler transport requires a remote endpoint")
        if selection.endpoint_class == "remote" and not selection.remote_authorized:
            raise ValueError("remote prompt compiler is not authorized")
        if selection.endpoint_class == "remote" and not api_key:
            raise ValueError("remote prompt compiler credential unavailable")
        self.selection = selection
        self.api_key = api_key
        self.timeout_seconds = int(timeout_seconds)
        self._resolved_model: Optional[str] = None

    @staticmethod
    def _normalized_model_id(value: str) -> str:
        return "".join(ch.lower() for ch in value if ch.isalnum())

    def _request_model(self) -> str:
        if self.selection.endpoint_class == "remote":
            return self.selection.model
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
            if not model_id.startswith("/") and needle and needle in self._normalized_model_id(model_id)
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
                "json_schema": {"name": "capt_prompt_stage", "strict": True, "schema": dict(response_schema)},
            },
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        request = urllib.request.Request(
            self.selection.base_url + "/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
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


def _compiler_from_selection(selection: PromptCompilerSelection):
    from capt_runtime.prompt_compiler import BoundedPromptCompilerRunner, CompilerProvider, PromptCompiler

    api_key = ""
    if selection.endpoint_class == "remote":
        api_key = resolve_secret(selection.provider_id, selection.key_ref)
        if not api_key:
            return None
    governor = TokenCostGovernor(
        max_tokens_per_session=131_072,
        max_cost_usd_per_session=0.01,
        max_requests_per_session=32,
        max_output_tokens_per_request=4096,
    )
    return PromptCompiler(
        runner=BoundedPromptCompilerRunner(
            OpenAICompatiblePromptCompilerTransport(selection, api_key=api_key), governor=governor
        ),
        provider=CompilerProvider(selection.provider_id, selection.model, selection.endpoint_class),
        remote_compilation_authorized=selection.remote_authorized,
    )


class FailoverPromptCompiler:
    """Try configured compiler preferences in order without weakening authority checks."""

    def __init__(self, compilers: list[Any]) -> None:
        self._compilers = tuple(compilers)

    def compile(self, request):
        last_error: Optional[BaseException] = None
        for compiler in self._compilers:
            try:
                return compiler.compile(request)
            except AuthorityViolation:
                raise
            except (OSError, TimeoutError, ValueError) as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise ValueError("no configured prompt compiler available")


def build_prompt_compiler(ui_config_dir: Path):
    """Construct the ordered Prompt Intelligence compiler preference chain."""
    compilers = []
    for selection in select_prompt_compiler_preferences(Path(ui_config_dir)):
        compiler = _compiler_from_selection(selection)
        if compiler is not None:
            compilers.append(compiler)
    if not compilers:
        return None
    return compilers[0] if len(compilers) == 1 else FailoverPromptCompiler(compilers)


def build_local_prompt_compiler(ui_config_dir: Path):
    """Backward-compatible local-only factory used by tests and safe fallback callers."""
    selection = select_local_prompt_compiler(Path(ui_config_dir))
    return _compiler_from_selection(selection) if selection is not None else None
