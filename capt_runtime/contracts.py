"""Contract binding loader and canonicalization helpers.

The runtime consumes the GENERATED Python bindings. It never re-implements a
schema rule, so contract drift cannot silently diverge from runtime behaviour.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

_GENERATED = Path(__file__).resolve().parent.parent / "contracts" / "generated" / "python"
if str(_GENERATED) not in sys.path:
    sys.path.insert(0, str(_GENERATED))

from capt_contracts import (  # noqa: E402  # type: ignore[import-not-found]
    CONTRACT_SCHEMA_VERSION,
    SPEC,
    known_types,
    validate,
)

from .errors import ContractViolation  # noqa: E402

__all__ = [
    "CONTRACT_SCHEMA_VERSION",
    "SPEC",
    "canonical_json",
    "digest",
    "known_types",
    "require",
    "validate",
]


def canonical_json(value: Any) -> str:
    """Deterministic serialization used for every digest in the runtime."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def require(type_name: str, value: Dict[str, Any]) -> Dict[str, Any]:
    """Validate against the generated contract or raise ContractViolation."""
    errors: List[str] = validate(type_name, value)
    if errors:
        raise ContractViolation(type_name, errors)
    return value
