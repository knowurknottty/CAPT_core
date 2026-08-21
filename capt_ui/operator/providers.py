"""Provider Manager (UI-1 / Phase 2).

Thin client-side provider registry + health probing. This is operator
configuration and connectivity, NOT runtime authority. It never mutates the
CAPT ledger and never duplicates RuntimeService logic.

Each provider exposes: connection, authentication, health, installed models,
capabilities, latency, context size, current selection, last success.

Privacy rule: never silently send prompts to a cloud provider when a local
provider is selected. API keys are stored by key-id reference.
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

from .contract import ProviderHealth, ProviderKind
from .secrets import is_reference


@dataclass
class Provider:
    id: str
    name: str
    kind: ProviderKind
    transport: str  # "openai_compatible" | "native" | "subprocess"
    base_url: str = ""
    key_ref: str = ""  # reference to a secret, never the raw key
    context_limit: int = 0
    enabled: bool = True
    selected: bool = False
    # health
    reachable: Optional[bool] = None
    authenticated: Optional[bool] = None
    model_list_ok: Optional[bool] = None
    latency_ms: Optional[int] = None
    last_success_at: Optional[str] = None
    health: ProviderHealth = ProviderHealth.UNKNOWN
    models: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind.value,
            "transport": self.transport,
            "base_url": self.base_url,
            "key_ref": self.key_ref,
            "context_limit": self.context_limit,
            "enabled": self.enabled,
            "selected": self.selected,
            "health": self.health.value,
            "latency_ms": self.latency_ms,
            "last_success_at": self.last_success_at,
            "models": self.models,
            "capabilities": self.capabilities,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Provider":
        return cls(
            id=d.get("id", ""),
            name=d.get("name", ""),
            kind=ProviderKind(d.get("kind", "unknown")),
            transport=d.get("transport", ""),
            base_url=d.get("base_url", ""),
            key_ref=d.get("key_ref", ""),
            context_limit=d.get("context_limit", 0),
            enabled=d.get("enabled", True),
            selected=d.get("selected", False),
            health=ProviderHealth(d.get("health", "unknown")),
            latency_ms=d.get("latency_ms"),
            last_success_at=d.get("last_success_at"),
            models=list(d.get("models", [])),
            capabilities=list(d.get("capabilities", [])),
        )


# Default provider templates (user may Add/Edit/Remove).
DEFAULT_PROVIDERS: List[Dict[str, Any]] = [
    {"id": "openrouter", "name": "OpenRouter", "kind": "cloud",
     "transport": "openai_compatible", "base_url": "https://openrouter.ai/api/v1",
     "context_limit": 128000, "capabilities": ["chat", "tool_use", "vision"]},
    {"id": "ollama", "name": "Ollama", "kind": "local",
     "transport": "ollama", "base_url": "http://localhost:11434/v1",
     "context_limit": 8192, "capabilities": ["chat", "generate"]},
    {"id": "lmstudio", "name": "LM Studio", "kind": "local",
     "transport": "openai_compatible", "base_url": "http://localhost:1234/v1",
     "context_limit": 32768, "capabilities": ["chat", "tool_use"]},
    {"id": "vllm", "name": "vLLM", "kind": "hybrid",
     "transport": "openai_compatible", "base_url": "http://localhost:8000/v1",
     "context_limit": 32768, "capabilities": ["chat"]},
    {"id": "llamacpp", "name": "llama.cpp-server", "kind": "local",
     "transport": "openai_compatible", "base_url": "http://localhost:8080/v1",
     "context_limit": 8192, "capabilities": ["chat"]},
    {"id": "hermes", "name": "Hermes", "kind": "local",
     "transport": "subprocess", "base_url": "", "context_limit": 0,
     "capabilities": ["bounded_execution"]},
]


def _validate_provider_config(provider: Provider) -> None:
    """Reject unsafe persisted config before a health probe can consume it.

    Provider config is an operator preference, not RuntimeService authority, but
    it still must never persist a raw secret or an ambiguous endpoint.
    """
    if provider.key_ref and not is_reference(provider.key_ref):
        raise ValueError("provider key_ref must be an env: or keychain: reference")
    if not provider.base_url:
        return
    parsed = urlsplit(provider.base_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("provider base_url must be an absolute http(s) URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("provider base_url must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("provider base_url must not contain query or fragment")


class ProviderManager:
    """Persisted provider registry + health probing (thin client)."""

    def __init__(self, config_dir: Optional[Path] = None) -> None:
        cfg = config_dir or self._default_config_dir()
        self._file = cfg / "providers.json"
        self._providers: Dict[str, Provider] = {}
        self._load_defaults()

    @staticmethod
    def _default_config_dir() -> Path:
        override = os.environ.get("CAPT_SOLO_HOME") or os.environ.get("CAPT_STATE_DIR")
        if override:
            return Path(override).expanduser() / "ui"
        return Path.home() / ".capt" / "ui"

    def _load_defaults(self) -> None:
        loaded_existing = False
        changed = False
        if self._file.exists():
            try:
                data = json.loads(self._file.read_text())
                for pd in data.get("providers", []):
                    p = Provider.from_dict(pd)
                    _validate_provider_config(p)
                    if (
                        p.id == "mlx" and p.transport == "native"
                        and not p.base_url and not p.key_ref and not p.models
                    ):
                        changed = True
                        continue
                    self._providers[p.id] = p
                loaded_existing = True
            except Exception:  # noqa: BLE001 - corrupt file: fall back to defaults
                self._providers.clear()

        for tmpl in DEFAULT_PROVIDERS:
            if tmpl["id"] in self._providers:
                continue
            self._providers[tmpl["id"]] = Provider.from_dict(tmpl)
            changed = loaded_existing or changed

        if loaded_existing and changed:
            self.save()

    def save(self) -> None:
        self._file.parent.mkdir(parents=True, exist_ok=True)
        payload = {"providers": [p.to_dict() for p in self._providers.values()]}
        self._file.write_text(json.dumps(payload, indent=2))

    # -- CRUD -------------------------------------------------------------
    def list(self) -> List[Provider]:
        return sorted(self._providers.values(), key=lambda p: (not p.selected, p.kind.value, p.id))

    def get(self, provider_id: str) -> Optional[Provider]:
        return self._providers.get(provider_id)

    def add(self, provider: Provider) -> None:
        _validate_provider_config(provider)
        self._providers[provider.id] = provider
        self.save()

    def update(self, provider_id: str, changes: Dict[str, Any]) -> Optional[Provider]:
        p = self._providers.get(provider_id)
        if p is None:
            return None
        candidate = deepcopy(p)
        for k, v in changes.items():
            if k in ("id",):
                continue
            if k == "kind":
                v = ProviderKind(v)
            elif k == "health":
                v = ProviderHealth(v)
            setattr(candidate, k, v)
        _validate_provider_config(candidate)
        self._providers[provider_id] = candidate
        self.save()
        return candidate

    def remove(self, provider_id: str) -> Optional[Provider]:
        p = self._providers.pop(provider_id, None)
        if p:
            self.save()
        return p

    def activate(self, provider_id: str) -> Optional[Provider]:
        target = self._providers.get(provider_id)
        if target is None:
            return None
        for p in self._providers.values():
            p.selected = False
        target.selected = True
        target.enabled = True
        self.save()
        return target

    def deactivate(self, provider_id: str) -> Optional[Provider]:
        p = self._providers.get(provider_id)
        if p is None:
            return None
        p.enabled = False
        p.selected = False
        self.save()
        return p

    # -- local/remote label -----------------------------------------------
    @staticmethod
    def label(provider: Provider) -> str:
        return {"local": "LOCAL", "cloud": "REMOTE", "hybrid": "HYBRID"}.get(
            provider.kind.value, "UNKNOWN"
        )

    def active_model_source(self) -> str:
        for p in self._providers.values():
            if p.selected:
                return self.label(p)
        return "UNKNOWN"

    # -- health probing ----------------------------------------------------
    def test(self, provider_id: str, api_key: str = "") -> Provider:
        """Probe provider connectivity (reachable, auth, models, latency)
        routed through the provider's TRANSPORT ADAPTER. Native/subprocess
        providers that lack an HTTP probe are classified honestly."""
        p = self._providers.get(provider_id)
        if p is None:
            raise ValueError("unknown provider: %s" % provider_id)
        from .adapters import adapter_for, resolve_secret

        adapter = adapter_for(getattr(p, "transport", ""))
        key = resolve_secret(p, api_key)
        try:
            result = adapter.health(p, key)
        except Exception as exc:  # noqa: BLE001 - adapter raised unexpectedly
            result = {"health": ProviderHealth.RED.value, "reachable": False,
                      "model_list_ok": False, "note": str(exc)[:100]}
        p.health = ProviderHealth(result.get("health", ProviderHealth.UNKNOWN.value))
        p.reachable = result.get("reachable")
        p.authenticated = result.get("authenticated")
        p.model_list_ok = result.get("model_list_ok", False)
        p.latency_ms = result.get("latency_ms")
        p.models = list(result.get("models", []))
        if result.get("health") == ProviderHealth.GREEN.value:
            p.last_success_at = _now()
        self.save()
        return p

    def prewarm(self, provider_id: str, model_id: str) -> Dict[str, Any]:
        """Warm a selected loopback OpenAI-compatible provider without ledger mutation.

        This is operator-plane readiness work, analogous to a health probe. The
        response is discarded and must never be promoted to CAPT evidence.
        """
        p = self._providers.get(provider_id)
        if p is None:
            raise ValueError("unknown provider: %s" % provider_id)
        if p.kind != ProviderKind.LOCAL or p.transport != "openai_compatible":
            raise ValueError("prewarm requires a local OpenAI-compatible provider")
        from capt_runtime.provider_endpoint import endpoint_class
        if endpoint_class(p.base_url) != "local":
            raise ValueError("prewarm requires a loopback endpoint")
        model = str(model_id or "").strip()
        if not model:
            raise ValueError("prewarm requires a model id")

        import time
        import urllib.request
        from .adapters import resolve_secret

        body = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": "CAPT provider prewarm. Reply OK."}],
            "max_tokens": 8,
            "temperature": 0,
            "stream": False,
        }).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        key = resolve_secret(p, "")
        if key:
            headers["Authorization"] = "Bearer " + key
        req = urllib.request.Request(
            p.base_url.rstrip("/") + "/chat/completions",
            data=body, headers=headers, method="POST",
        )
        started = time.monotonic()
        with urllib.request.urlopen(req, timeout=120) as response:
            response.read()
        return {
            "status": "warm",
            "provider": p.id,
            "model": model,
            "endpoint_class": "local",
            "latency_ms": int((time.monotonic() - started) * 1000),
        }

    # -- discovery ---------------------------------------------------------
    def discover_local(self) -> List[str]:
        """Return ids of local providers whose transport adapter detected a
        reachable service. Uses the correct adapter per provider - never forces
        an HTTP probe on a native/subprocess provider."""
        from .adapters import adapter_for
        found = []
        for pid in ("ollama", "lmstudio", "llamacpp"):
            p = self._providers.get(pid)
            if not p or not p.enabled:
                continue
            adapter = adapter_for(getattr(p, "transport", ""))
            try:
                if adapter.discover(p):
                    found.append(pid)
            except Exception:  # noqa: BLE001
                continue
        return found


def _now() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")