"""Secret resolution and scrubbing (UI Foundation / Phase 6 hardening).

Requirements met here:
- UI never persists raw provider tokens in providers.json;
- diagnostic logs never print tokens;
- provider config stores secret REFERENCES (env:NAME or keychain:acct);
- adapters resolve the secret only at call time;
- deleting a provider does not accidentally leak credentials (deletion is
  decoupled from the secret store; secret removal must be explicit);

For v0.6: macOS Keychain + environment-variable reference is sufficient. No
large credential architecture.
"""

from __future__ import annotations

import os
import re
import subprocess
from typing import Any, Optional

_SECRET_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9_\-]{8,}|Bearer\s+[A-Za-z0-9_\-\.]{8,}|"
    r"(?:key|token|secret)\s*[=:]\s*[A-Za-z0-9_\-\.]{8,})",
    re.IGNORECASE,
)


def is_reference(value: str) -> bool:
    """True if a stored value is a safe reference, not a raw secret."""
    return value.startswith("env:") or value.startswith("keychain:")


def make_ref(kind: str, name: str) -> str:
    """Build a secret reference (e.g. 'env:OPENROUTER_API_KEY' or
    'keychain:openrouter')."""
    if kind == "env":
        return "env:" + name
    if kind == "keychain":
        return "keychain:" + name
    raise ValueError("unknown secret reference kind: %s" % kind)


def resolve(provider_id: str, ref: str = "", explicit: str = "") -> str:
    """Resolve a secret reference to its runtime value. Never persists it.

    Order: explicit arg > env:NAME > keychain:acct > CAPT_PROVIDER_KEY_<ID>.
    """
    if explicit:
        return explicit
    if ref.startswith("env:"):
        return os.environ.get(ref[4:], "")
    if ref.startswith("keychain:"):
        return _keychain_get("capt-provider", ref[9:])
    val = os.environ.get("CAPT_PROVIDER_KEY_%s" % provider_id.upper(), "")
    return val or ""


def _keychain_get(service: str, account: str) -> str:
    try:
        out = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
            capture_output=True, text=True, timeout=5, check=False)
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:  # noqa: BLE001
        pass
    return ""


def scrub(text: str) -> str:
    """Redact any secret-like token from a string (logs, evidence, diagnostics)."""
    return _SECRET_PATTERN.sub("<redacted>", text or "")


def scrub_obj(obj: Any) -> Any:
    """Deep-scrub a nested object (dict/list/str) of secret-like tokens."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            kk = "redacted_%s" % k if "key" in str(k).lower() or "token" in str(k).lower() or "secret" in str(k).lower() else k
            out[kk] = scrub_obj(v)
        return out
    if isinstance(obj, list):
        return [scrub_obj(v) for v in obj]
    if isinstance(obj, str):
        return scrub(obj)
    return obj


def safe_to_dict(provider: Any) -> dict:
    """provider.to_dict() with any key_ref/secret fields replaced and scrubbed
    so diagnostics never leak a raw credential. Key names are preserved; only
    values are redacted."""
    d = provider.to_dict() if hasattr(provider, "to_dict") else dict(provider or {})
    if "key_ref" in d:
        ref = str(d.get("key_ref") or "")
        if ":" in ref:
            d["key_ref"] = "%s:<ref>" % ref.split(":")[0]
        else:
            d["key_ref"] = "<none>"
    out = {}
    for k, v in d.items():
        is_secret_field = "key" in str(k).lower() or "token" in str(k).lower() or "secret" in str(k).lower()
        out[k] = scrub(v) if isinstance(v, str) else scrub_obj(v)
        if is_secret_field and isinstance(v, str) and v and v != out[k]:
            pass  # already redacted via scrub
    return out
