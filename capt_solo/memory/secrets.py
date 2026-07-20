"""CAPT Solo v0.2 — secret and sensitive-data screening.

Deterministic, dependency-free screening of likely secrets before persistence
and export. This is NOT perfect detection — it uses high-precision pattern
matches for well-known secret shapes. False negatives are possible; the docs
state this explicitly. Default behavior: reject or redact, never silently store.

Fidelity rule: secrets are never included in AntiToken output, logs, exports,
receipts, or error traces.
"""

from __future__ import annotations

import re
from typing import List, Tuple

from capt_solo.memory.models import StageResult

# High-precision patterns. Each is conservative to avoid excessive false positives.
_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("aws_secret", re.compile(r"(?i)aws_secret_access_key\s*[:=]\s*['\"]?[A-Za-z0-9/+]{40}")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("bearer_token", re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{20,}")),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("stripe_key", re.compile(r"(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}")),
    ("google_api", re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("password_assign", re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?[^\s'\"]{6,}")),
    ("api_key_assign", re.compile(r"(?i)(api[_-]?key|apikey|secret[_-]?key)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}")),
    ("auth_cookie", re.compile(r"(?i)(session|auth|access)[_\-]?token\s*[:=]\s*['\"]?[A-Za-z0-9._\-]{20,}")),
    ("recovery_code", re.compile(r"(?i)recovery[_-]?code\s*[:=]\s*['\"]?[A-Za-z0-9]{8,}")),
    ("seed_phrase", re.compile(r"(?i)(seed\s*phrase|mnemonic|recovery\s*phrase)\b")),
    ("env_secret", re.compile(
        r"(?i)(?:^|\n)\s*(?:export\s+)?[A-Z][A-Z0-9_]{2,}\s*=\s*['\"]?[A-Za-z0-9/+_\-]{20,}['\"]?\s*(?:\n|$)")),
]


def _redact_match(text: str, pat: re.Pattern, label: str) -> str:
    def _sub(m):
        matched = m.group(0)
        # keep a short prefix for audit, redact the rest
        if len(matched) > 12:
            return matched[:8] + "[" + label + "-REDACTED]"
        return "[" + label + "-REDACTED]"
    return pat.sub(_sub, text)


def screen(text: str) -> Tuple[bool, List[str], str]:
    """Return (has_secret, reasons, redacted_text).

    ``has_secret`` is True if any high-precision pattern matched. The redacted
    text replaces matched secrets with a marker so the user can still store a
    sanitized version if they explicitly override.
    """
    reasons: List[str] = []
    redacted = text
    for label, pat in _PATTERNS:
        if pat.search(text):
            reasons.append(f"possible {label} detected")
            redacted = _redact_match(redacted, pat, label)
    return (len(reasons) > 0, reasons, redacted)


def secret_screening_stage(content: str, *, allow_secrets: bool = False) -> StageResult:
    """Pipeline stage: screen for secrets.

    Default: if a secret is detected, the stage fails (rejection) and returns a
    redacted copy in ``value['redacted']``. Caller may retry with
    ``allow_secrets=True`` for an explicit, narrowly scoped override — but the
    redaction marker is still recorded in provenance.
    """
    has_secret, reasons, redacted = screen(content)
    res = StageResult(stage="secret_screening", ok=True,
                       value={"redacted": redacted, "has_secret": has_secret})
    if has_secret and not allow_secrets:
        res.ok = False
        for r in reasons:
            res.add_rejection(r)
        res.provenance_changes["secret_redaction_required"] = True
    elif has_secret and allow_secrets:
        res.add_warning("secret stored despite detection (explicit override)")
        res.provenance_changes["secret_stored_with_override"] = True
    return res
