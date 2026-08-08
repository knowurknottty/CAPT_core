"""Transport-specific provider adapters (UI Foundation / Phase 2 hardening).

A thin plugin-style contract so the generic OpenAI-compatible /models path is not
incorrectly forced onto native/subprocess providers. Only adapters with real
behavior are implemented; the rest fall back to an honest 'not implemented'
status.

Adapter contract (Protocol):
    discover(...)         -> bool (was a local provider detected)
    health(...)           -> dict (reachable, authenticated, latency, ...)
    list_models(...)      -> list[str]
    capabilities(...)     -> list[str]
    execute_or_bind(...)  -> callable / bound executor (or raises NotSupported)

Each adapter owns a single transport. ProviderManager routes to the right
adapter by `Provider.transport`.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol

from .contract import ProviderHealth


class AdapterNotSupported(NotImplementedError):
    """Raised when an adapter/operation is not implemented for a transport."""


class ProviderAdapter(Protocol):
    transport: str

    def discover(self, provider: Any) -> bool: ...

    def health(self, provider: Any, api_key: str = "") -> Dict[str, Any]: ...

    def list_models(self, provider: Any, api_key: str = "") -> List[str]: ...

    def capabilities(self) -> List[str]: ...

    def execute_or_bind(self, provider: Any, model: str,
                        api_key: str = "") -> Callable[..., Any]: ...


class OpenAICompatibleAdapter:
    """Covers OpenRouter, LM Studio, vLLM, llama.cpp-server, and any
    OpenAI-compatible endpoint. Uses GET /models for discovery + health."""

    transport = "openai_compatible"

    def discover(self, provider: Any) -> bool:
        return self._probe_ok(provider.base_url, None)

    def health(self, provider: Any, api_key: str = "") -> Dict[str, Any]:
        start = time.time()
        try:
            models = self.list_models(provider, api_key)
            latency = int((time.time() - start) * 1000)
            return {
                "health": ProviderHealth.GREEN.value,
                "reachable": True, "authenticated": True,
                "model_list_ok": True, "latency_ms": latency,
                "models": models,
            }
        except urllib.error.HTTPError as exc:
            latency = int((time.time() - start) * 1000)
            if exc.code in (401, 403):
                return {"health": ProviderHealth.RED.value, "reachable": True,
                        "authenticated": False, "model_list_ok": False,
                        "latency_ms": latency}
            return {"health": ProviderHealth.YELLOW.value, "reachable": True,
                    "authenticated": True, "model_list_ok": False,
                    "latency_ms": latency}
        except Exception:  # noqa: BLE001
            latency = int((time.time() - start) * 1000)
            return {"health": ProviderHealth.RED.value, "reachable": False,
                    "authenticated": None, "model_list_ok": False,
                    "latency_ms": latency}

    def list_models(self, provider: Any, api_key: str = "") -> List[str]:
        headers = {"Accept": "application/json"}
        key = _resolve_key(provider, api_key)
        if key:
            headers["Authorization"] = "Bearer " + key
        url = provider.base_url.rstrip("/") + "/models"
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=4) as resp:  # noqa: S310
            data = json.loads(resp.read().decode())
        return [m.get("id", "") for m in data.get("data", []) if m.get("id")]

    def capabilities(self) -> List[str]:
        return ["chat", "completion"]

    def execute_or_bind(self, provider: Any, model: str, api_key: str = "") -> Callable[..., Any]:
        raise AdapterNotSupported(
            "OpenAI-compatible model execution adapter is not wired into a CAPT "
            "governed driver yet (P1; real-model mission is separate release-gate work)."
        )

    def _probe_ok(self, base_url: str, key: Optional[str]) -> bool:
        try:
            self.list_models(type("_p", (), {"base_url": base_url})())  # type: ignore
            return True
        except Exception:  # noqa: BLE001
            return False


def _resolve_key(provider: Any, api_key: str = "") -> str:
    """Resolve a provider secret through the shared secrets layer. Never prints
    or persists the raw key."""
    from .secrets import resolve as _resolve_secret
    pid = str(getattr(provider, "id", ""))
    ref = str(getattr(provider, "key_ref", "") or "")
    return _resolve_secret(pid, ref, api_key)


class OllamaAdapter:
    """Native Ollama HTTP API (/api/tags) plus OpenAI-compatible compatibility."""

    transport = "ollama"

    def discover(self, provider: Any) -> bool:
        try:
            self.list_models(provider)
            return True
        except Exception:  # noqa: BLE001
            return False

    def health(self, provider: Any, api_key: str = "") -> Dict[str, Any]:
        start = time.time()
        try:
            models = self.list_models(provider)
            latency = int((time.time() - start) * 1000)
            return {"health": ProviderHealth.GREEN.value, "reachable": True,
                    "authenticated": True, "model_list_ok": True,
                    "latency_ms": latency, "models": models}
        except Exception:  # noqa: BLE001
            latency = int((time.time() - start) * 1000)
            return {"health": ProviderHealth.RED.value, "reachable": False,
                    "authenticated": None, "model_list_ok": False,
                    "latency_ms": latency}

    def list_models(self, provider: Any, api_key: str = "") -> List[str]:
        base = provider.base_url.replace("/v1", "").rstrip("/")
        url = base + "/api/tags"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=4) as resp:  # noqa: S310
            data = json.loads(resp.read().decode())
        return [m.get("name", "") for m in data.get("models", []) if m.get("name")]

    def capabilities(self) -> List[str]:
        return ["chat", "generate"]

    def execute_or_bind(self, provider: Any, model: str, api_key: str = "") -> Callable[..., Any]:
        raise AdapterNotSupported(
            "Ollama execution adapter not wired into a governed CAPT driver (P1).")


class NativeAdapter:
    """Native providers (MLX/mlx_lm) that are NOT HTTP-probable. Honest
    'not implemented' for health/model list until a real local discovery or
    subprocess integration exists."""

    transport = "native"

    def discover(self, provider: Any) -> bool:
        return False  # no HTTP/probe path; not pretending

    def health(self, provider: Any, api_key: str = "") -> Dict[str, Any]:
        return {"health": ProviderHealth.UNKNOWN.value, "reachable": None,
                "authenticated": None, "model_list_ok": False,
                "latency_ms": None, "note": "native adapter not implemented"}

    def list_models(self, provider: Any, api_key: str = "") -> List[str]:
        return []

    def capabilities(self) -> List[str]:
        return []

    def execute_or_bind(self, provider: Any, model: str, api_key: str = "") -> Callable[..., Any]:
        raise AdapterNotSupported("native (MLX/mlx_lm) execution adapter not implemented")


class SubprocessAdapter:
    """Hermes-style subprocess compatibility. Bounded; never makes Hermes a
    runtime-authority."""

    transport = "subprocess"

    def discover(self, provider: Any) -> bool:
        return bool(os.environ.get("HERMES_EXECUTABLE") or _which("hermes"))

    def health(self, provider: Any, api_key: str = "") -> Dict[str, Any]:
        return {"health": ProviderHealth.YELLOW.value if self.discover(provider) else ProviderHealth.RED.value,
                "reachable": bool(self.discover(provider)),
                "authenticated": True, "model_list_ok": False,
                "latency_ms": None, "note": "subprocess compatibility via bounded bridge"}

    def list_models(self, provider: Any, api_key: str = "") -> List[str]:
        return []

    def capabilities(self) -> List[str]:
        return ["bounded_execution"]

    def execute_or_bind(self, provider: Any, model: str, api_key: str = "") -> Callable[..., Any]:
        # Hermes is a bounded execution driver; reuse the established bridge
        # boundary. This binding returns a callable that raises unless a
        # governed work order is provided - it never runs ungoverned.
        from desktop.desktop_runtime_client import RuntimeClient  # noqa: F401
        raise AdapterNotSupported(
            "Hermes subprocess execution requires a governed CAPT work order; "
            "not exposed as an ungoverned chat binding.")


def _which(name: str) -> Optional[str]:
    import shutil
    return shutil.which(name)


def adapter_for(transport: str) -> ProviderAdapter:
    mapping = {
        "openai_compatible": OpenAICompatibleAdapter(),
        "ollama": OllamaAdapter(),
        "native": NativeAdapter(),
        "subprocess": SubprocessAdapter(),
    }
    return mapping.get(transport, NativeAdapter())  # unknown -> honest not-implemented


def health_via_adapter(provider: Any, api_key: str = "") -> Dict[str, Any]:
    """Route a provider's health check through its transport adapter."""
    a = adapter_for(getattr(provider, "transport", ""))
    return a.health(provider, api_key)


def list_models_via_adapter(provider: Any, api_key: str = "") -> List[str]:
    a = adapter_for(getattr(provider, "transport", ""))
    return a.list_models(provider, api_key)


def resolve_secret(provider: Any, api_key: str = "") -> str:
    """Public secret-resolution entry point (testable)."""
    return _resolve_key(provider, api_key)
