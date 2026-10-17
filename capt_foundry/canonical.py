"""Deterministic primitives for Foundry records.

Canonical serialization and digest form are deliberately IDENTICAL to
``capt_runtime.contracts`` (sorted keys, tight separators, ``sha256:`` prefix) so
a Foundry digest and a runtime digest of the same value agree. The functions are
re-implemented rather than imported because ``capt_runtime.contracts`` loads the
generated contract bindings at import time, and the Foundry must not require the
runtime's contract package to be present merely to hash a dict. Byte-identical
agreement is asserted by test_canonical.py rather than assumed.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
import unicodedata
from typing import Any

FOUNDRY_SCHEMA_VERSION = "capt-foundry.v1"

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_RFC3339_Z_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,9})?Z$"
)
# Mirrors contracts/schema/common.schema.json#/$defs/Identifier.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")

GENESIS_DIGEST = "sha256:" + "0" * 64


def canonical_json(value: Any) -> str:
    """Deterministic serialization. Matches capt_runtime.contracts.canonical_json."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    """sha256 over the canonical form, algorithm-prefixed."""
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def digest_bytes(data: bytes) -> str:
    """sha256 over raw bytes — used for document content, never for records."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


def is_digest(value: Any) -> bool:
    return isinstance(value, str) and bool(_DIGEST_RE.match(value))


def is_rfc3339_z(value: Any) -> bool:
    return isinstance(value, str) and bool(_RFC3339_Z_RE.match(value))


def is_identifier(value: Any) -> bool:
    return isinstance(value, str) and bool(_IDENTIFIER_RE.match(value))


def utc_now() -> str:
    """RFC3339 UTC to whole seconds. Descriptive only, never used for ordering."""
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_name(name: str) -> str:
    """Fold a name for alias lookup.

    NFKC, casefold, collapse internal whitespace, strip. Deliberately
    conservative: it does NOT strip punctuation, drop diacritics beyond NFKC, or
    reorder tokens, because those transforms merge genuinely distinct research
    subjects. Distinctness is preserved in favour of recall; ambiguity is
    surfaced as AmbiguousAlias rather than silently resolved.
    """
    folded = unicodedata.normalize("NFKC", name).casefold().strip()
    return " ".join(folded.split())
