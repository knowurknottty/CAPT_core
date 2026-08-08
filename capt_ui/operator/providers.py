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
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .contract import ProviderHealth, ProviderKind


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
     "transport": "openai_compatible", "base_url": "http://localhost:11434/v1",
     "context_limit": 8192, "capabilities": ["chat"]},
    {"id": "lmstudio", "name": "LM Studio", "kind": "local",
     "transport": "openai_compatible", "base_url": "http://localhost:1234/v1",
     "context_limit": 32768, "capabilities": ["chat", "tool_use"]},
    {"id": "mlx", "name": "MLX / mlx_lm", "kind": "local",
     "transport": "native", "base_url": "", "context_limit": 32768,
     "capabilities": ["chat"]},
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
        if self._file.exists():
            try:
                data = json.loads(self._file.read_text())
                for pd in data.get("providers", []):
                    p = Provider.from_dict(pd)
                    self._providers[p.id] = p
                return
            except Exception:  # noqa: BLE001 - corrupt file: fall back to defaults
                pass
        for tmpl in DEFAULT_PROVIDERS:
            p = Provider.from_dict(tmpl)
            self._providers[p.id] = p

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
        self._providers[provider.id] = provider
        self.save()

    def update(self, provider_id: str, changes: Dict[str, Any]) -> Optional[Provider]:
        p = self._providers.get(provider_id)
        if p is None:
            return None
        for k, v in changes.items():
            if k in ("id",):
                continue
            if k == "kind":
                v = ProviderKind(v)
            elif k == "health":
                v = ProviderHealth(v)
            setattr(p, k, v)
        self.save()
        return p

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
        """Probe provider connectivity (reachable, auth, models, latency)."""
        p = self._providers.get(provider_id)
        if p is None:
            raise ValueError("unknown provider: %s" % provider_id)
        start = time.time()
        try:
            models, ctx = self._fetch_models(p, api_key)
            latency = int((time.time() - start) * 1000)
            p.reachable = True
            p.model_list_ok = True
            p.authenticated = True  # no auth error observed
            p.latency_ms = latency
            p.last_success_at = _now()
            p.models = models
            if ctx:
                p.context_limit = ctx
            p.health = ProviderHealth.GREEN
        except urllib.error.HTTPError as exc:
            p.reachable = True
            p.model_list_ok = False
            if exc.code in (401, 403):
                p.authenticated = False
                p.health = ProviderHealth.RED
            else:
                p.authenticated = True
                p.health = ProviderHealth.YELLOW
            p.latency_ms = int((time.time() - start) * 1000)
        except Exception:  # noqa: BLE001 - unreachable
            p.reachable = False
            p.authenticated = None
            p.model_list_ok = False
            p.health = ProviderHealth.RED
            p.latency_ms = int((time.time() - start) * 1000)
        self.save()
        return p

    # -- discovery ---------------------------------------------------------
    def discover_local(self) -> List[str]:
        """Return ids of local providers whose endpoint answered a probe."""
        found = []
        for pid in ("ollama", "lmstudio", "llamacpp"):
            p = self._providers.get(pid)
            if not p or not p.base_url:
                continue
            try:
                self._fetch_models(p)
                found.append(pid)
            except Exception:  # noqa: BLE001
                continue
        return found

    # -- internals ---------------------------------------------------------
    def _fetch_models(self, p: Provider, api_key: str = "") -> tuple:
        """Return (model_names, context_size). Handles OpenAI-compatible servers."""
        url = p.base_url.rstrip("/") + "/models"
        headers: Dict[str, str] = {"Accept": "application/json"}
        key = api_key or os.environ.get("CAPT_PROVIDER_KEY_%s" % p.id.upper(), "")
        if key:
            headers["Authorization"] = "Bearer " + key
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=4) as resp:  # noqa: S310 - local/cloud HTTPS ok
            data = json.loads(resp.read().decode())
        model_names = [m.get("id", "") for m in data.get("data", []) if m.get("id")]
        ctx = 0
        # best-effort context from the largest counted model
        for m in data.get("data", []):
            try:
                c = int((m.get("context_length") or m.get("context_window") or 0))
                ctx = max(ctx, c)
            except (TypeError, ValueError):
                pass
        return model_names, ctx


def _now() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")