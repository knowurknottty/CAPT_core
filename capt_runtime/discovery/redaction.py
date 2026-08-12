"""Bounded secret redaction for discovery evidence (v0.7).

Conservatively marks credential-shaped substrings. It does NOT claim exhaustive
secret detection; output should be described as "redacted potential secret",
never "all secrets removed" unless that is separately proven.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Sequence


_SECRET_NAME_RE = re.compile(
    r"(token|secret|password|passwd|api[_-]?key|auth|bearer|private[_-]?key|"
    r"nonce|fencing[_-]?token|credential|signing[_-]?key|client[_-]?secret|"
    r"OPENAI|OPENROUTER|ANTHROPIC|AWS|GITHUB)",
    re.IGNORECASE,
)
_LONG_HEX_RE = re.compile(r"\b[0-9a-f]{40,}\b", re.IGNORECASE)
_LONG_B58_RE = re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{40,}\b")
_LONG_B64_RE = re.compile(r"\b[0-9A-Za-z+/]{40,}={0,2}\b")
# e.g. sk-..., ghp_..., AKIA..., aws_secret_access_key = XXXX
_PREFIXED_SK_RE = re.compile(
    r"\b(sk-[A-Za-z0-9_-]{6,}|gh[pousr]_[A-Za-z0-9]{16,}|"
    r"AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{6,})\b"
)


def redact_text(text: str) -> str:
    """Replace credential-shaped substrings with a redaction marker."""
    out = _LONG_B64_RE.sub("[REDACTED_B64]", text)
    out = _LONG_HEX_RE.sub("[REDACTED_HEX]", out)
    out = _LONG_B58_RE.sub("[REDACTED_B58]", out)
    out = _PREFIXED_SK_RE.sub("[REDACTED_KEY]", out)
    # redact the assigned value of secret-named keys (common markup/ini/env)
    out = re.sub(
        r"(\b[A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|API[_]?KEY|KEY|PASSWD)"
        r"\b[\"']?\s*[:=]\s*[\"']?)[^\s\"',;}]+",
        r"\1[REDACTED]",
        out,
        flags=re.IGNORECASE,
    )
    # normalize home + repo roots
    home = str(Path.home())
    out = out.replace(home, "${HOME}")
    return out


def redact_jsonl(items: Sequence[str]) -> str:
    """Deterministic JSONL of redacted normalized paths/entries."""
    lines = []
    for it in items:
        lines.append(json.dumps({"path": normalize_path(redact_text(str(it)))},
                                sort_keys=True))
    return "\n".join(lines) + ("\n" if lines else "")


def normalize_path(path: str) -> str:
    p = str(Path(path).expanduser())
    home = str(Path.home())
    if p.startswith(home + os.sep):
        return "${HOME}" + p[len(home):]
    return p


def redact_json(obj: object) -> object:
    """Recursively redact string values in a JSON-serializable object."""
    if isinstance(obj, dict):
        return {k: redact_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redact_json(v) for v in obj]
    if isinstance(obj, str):
        return redact_text(obj)
    return obj
