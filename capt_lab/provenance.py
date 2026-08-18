"""Donor provenance loading and digest utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .contracts import LabContractError, canonical_json_bytes, sha256_digest

_MANIFEST = Path(__file__).resolve().parent / "donors" / "manifest.json"


def load_donor_manifest() -> Dict[str, Any]:
    try:
        value = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LabContractError("Lab donor manifest is unreadable") from exc
    if value.get("schemaVersion") != "1.0.0" or not isinstance(value.get("engines"), dict):
        raise LabContractError("Lab donor manifest has invalid shape")
    canonical_json_bytes(value)
    return value


def donor_for(engine_id: str) -> Dict[str, Any]:
    engines = load_donor_manifest()["engines"]
    if engine_id not in engines:
        raise LabContractError("no donor provenance for %s" % engine_id)
    return dict(engines[engine_id])


def manifest_digest() -> str:
    return sha256_digest(canonical_json_bytes(load_donor_manifest()))
