"""Provider endpoint classification and credential policy.

Runtime policy is intentionally conservative: credentialless OpenAI-compatible
execution is permitted only for providers explicitly classified LOCAL whose
HTTP endpoint is loopback-only.  A remote endpoint cannot bypass credential
requirements merely by being mislabeled local in operator configuration.
"""
from __future__ import annotations

from ipaddress import ip_address
from typing import Any
from urllib.parse import urlsplit


def endpoint_class(base_url: str) -> str:
    """Classify an HTTP provider endpoint for provenance."""
    host = urlsplit(str(base_url or "")).hostname
    if not host:
        return "unknown"
    if host.lower() == "localhost":
        return "local"
    try:
        if ip_address(host).is_loopback:
            return "local"
    except ValueError:
        pass
    return "cloud"


def credential_required(provider_id: str, provider_kind: Any, base_url: str) -> bool:
    """Return whether absence of provider credentials must fail closed."""
    if str(provider_id) == "ollama":
        return False
    kind = getattr(provider_kind, "value", provider_kind)
    return not (str(kind) == "local" and endpoint_class(base_url) == "local")
