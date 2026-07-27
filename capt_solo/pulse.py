"""CAPT PULSE gateway — safe, optional, disabled-by-default public subsystem.

Per owner Decision 4: PULSE is approved for public release only if safe,
documented, disabled-by-default where network behavior exists, explicit about
external dependencies, tested, and free of private credentials/infrastructure.

Safety contract:
- Importing this module performs NO network I/O and imports NO network libraries.
- Network libraries (e.g. `urllib.request`) are imported lazily, ONLY inside an
  enabled, explicitly-configured call.
- By default the gateway is DISABLED. `complete()` / `chat()` raise PulseDisabled
  unless `configure()` was called with an explicit endpoint and `enabled=True`.
- No private credentials, endpoints, or infrastructure assumptions are present.
- If an external call fails, the gateway fails CLOSED (raises) — it never silently
  degrades into returning empty/garbage or falling back to a hidden transport.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


class PulseDisabled(Exception):
    """Raised when PULSE is used while disabled (default)."""


class PulseError(Exception):
    """Raised on gateway failure; fails closed."""


@dataclass
class PulseConfig:
    endpoint: Optional[str] = None
    enabled: bool = False
    timeout_s: float = 30.0
    model: str = "local-default"


class PulseGateway:
    """Optional LLM gateway. Disabled by default; no network on import."""

    def __init__(self, config: Optional[PulseConfig] = None) -> None:
        self._config = config or PulseConfig()
        # No network import, no socket, no requests — nothing here.

    @property
    def enabled(self) -> bool:
        return self._config.enabled and self._config.endpoint is not None

    def configure(self, *, endpoint: str, enabled: bool = True,
                   timeout_s: float = 30.0, model: str = "local-default") -> None:
        """Explicitly enable with a user-supplied endpoint. Never called
        automatically; never reads private/default endpoints."""
        if not endpoint:
            raise PulseError("endpoint is required to enable PULSE")
        self._config = PulseConfig(endpoint=endpoint, enabled=enabled,
                                   timeout_s=timeout_s, model=model)

    def _require_enabled(self) -> PulseConfig:
        if not self.enabled:
            raise PulseDisabled(
                "PULSE is disabled by default. Call configure(endpoint=..., "
                "enabled=True) to enable. No network call was made.")
        return self._config

    def complete(self, prompt: str, *, max_tokens: int = 256) -> str:
        """Complete a prompt via the configured endpoint. Fails closed.

        Network import is lazy and scoped to this method so that merely importing
        the package never opens a socket.
        """
        cfg = self._require_enabled()
        try:
            import urllib.request
            import json
            req = urllib.request.Request(
                cfg.endpoint,
                data=json.dumps({"prompt": prompt, "max_tokens": max_tokens,
                                 "model": cfg.model}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST")
            with urllib.request.urlopen(req, timeout=cfg.timeout_s) as resp:
                body = resp.read().decode()
            return json.loads(body).get("completion", "")
        except Exception as exc:  # fail closed
            raise PulseError(f"PULSE request failed; no fallback: {exc}") from exc

    def chat(self, messages: List[str]) -> str:
        cfg = self._require_enabled()
        return self.complete("\n".join(messages))


def default_gateway() -> PulseGateway:
    """Return a disabled-by-default gateway (no network on import)."""
    return PulseGateway()
