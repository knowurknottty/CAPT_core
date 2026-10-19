"""Deterministic frozen-source coverage witnesses for strict council reviews.

Only the operator-provided source blocks define the manifest. Coverage rows
attest dispositions, NOT correctness; independent verification remains required.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

_MARKER = re.compile(r"^=== (BEGIN|END) ([^\r\n]+?) ===\s*$", re.MULTILINE)
_FILE_ROW = re.compile(r"^CAPT_SOURCE_FILE\s+(.+?)\s*\|\s*PRESENT\s*$", re.MULTILINE)
_ITEM_ROW = re.compile(r"^CAPT_SOURCE_ITEM\s+(CAPT-UPG-\d{3})\s*\|\s*DISPOSITION=(\S.*)$", re.MULTILINE)
_ID = re.compile(r"CAPT-UPG-\d{3}\Z")


def _ids_from_json(value: Any, found: list[str]) -> None:
    if isinstance(value, dict):
        candidate = value.get("id")
        if isinstance(candidate, str) and _ID.fullmatch(candidate):
            found.append(candidate)
        for nested in value.values():
            _ids_from_json(nested, found)
    elif isinstance(value, list):
        for item in value:
            _ids_from_json(item, found)


def frozen_source_manifest(objective: str) -> dict[str, Any] | None:
    """Parse the exact input text; fail closed on malformed markers or IDs."""
    markers = list(_MARKER.finditer(objective))
    if not markers:
        return None
    if len(markers) > 48 or len(markers) % 2:
        raise ValueError("FROZEN_SOURCE_BLOCKS_UNBALANCED")
    files: list[dict[str, Any]] = []
    ids: list[str] = []
    seen: set[str] = set()
    for start, end in zip(markers[::2], markers[1::2]):
        name = start.group(2)
        if start.group(1) != "BEGIN" or end.group(1) != "END" or end.group(2) != name:
            raise ValueError("FROZEN_SOURCE_BLOCKS_UNBALANCED")
        if name in seen or not name or len(name) > 256:
            raise ValueError("FROZEN_SOURCE_PATH_DUPLICATE_OR_INVALID")
        seen.add(name)
        body = objective[start.end():end.start()]
        data = body.encode("utf-8")
        if len(data) > 4_000_000:
            raise ValueError("FROZEN_SOURCE_BLOCK_TOO_LARGE")
        files.append({
            "path": name, "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        })
        if name.lower().endswith(".json") and "backlog" in name.lower():
            try:
                obj = json.loads(body)
            except (ValueError, TypeError) as exc:
                raise ValueError("FROZEN_SOURCE_BACKLOG_JSON_INVALID") from exc
            _ids_from_json(obj, ids)
    if len(set(ids)) != len(ids):
        raise ValueError("FROZEN_SOURCE_BACKLOG_IDS_DUPLICATED")
    disposition_requested = bool(re.search(
        r"(?i)(explicit\s+disposition\s+for\s+every|"
        r"disposition\s+for\s+(?:all|every)\s+\d+\s+backlog)",
        objective[:min(len(objective), 14000)],
    ))
    return {
        "files": files,
        "backlogIds": sorted(ids),
        "requiresDisposition": disposition_requested and bool(ids),
    }


def source_coverage_contract(objective: str) -> str:
    """Approval-time guidance for future strict council runs only."""
    manifest = frozen_source_manifest(objective)
    if not manifest or not manifest["requiresDisposition"]:
        return ""
    return (
        "\nCAPT FROZEN SOURCE FIDELITY CONTRACT (AFTER THE PHYSICAL CHARTER):\n"
        f"- The input contains {len(manifest['files'])} enclosed files "
        f"and {len(manifest['backlogIds'])} authoritative backlog IDs.\n"
        "- Emit one CAPT_SOURCE_FILE <exact path> | PRESENT row per enclosed file.\n"
        "- Emit one CAPT_SOURCE_ITEM <exact ID> | DISPOSITION=<specific decision "
        "and evidence> row per authoritative backlog record.\n"
        "- Do not claim an enclosed file or ID was missing or truncated. "
        "Declare PARTIAL rather than fabricate unavailable conclusions.\n"
        "- CAPT checks row coverage independently from charter geometry; "
        "the rows do not establish factual correctness.\n"
    )


def validate_source_coverage(objective: str, report: str) -> dict[str, Any]:
    """Count exact attestations; never infer coverage from 66/22 charter rows."""
    manifest = frozen_source_manifest(objective)
    if not manifest or not manifest["requiresDisposition"]:
        return {"required": False, "valid": True, "status": "not_required"}
    expected_files = {row["path"] for row in manifest["files"]}
    expected_ids = set(manifest["backlogIds"])
    files = [m.group(1).strip() for m in _FILE_ROW.finditer(report)]
    items = [(m.group(1), m.group(2).strip()) for m in _ITEM_ROW.finditer(report)]
    found_files = set(files)
    found_ids = {item_id for item_id, _ in items}
    ids = [item_id for item_id, _ in items]
    duplicates = lambda xs: sorted({x for x in xs if xs.count(x) > 1})
    invalid_dispositions = sorted({
        item_id for item_id, disposition in items
        if disposition.lower().startswith(("missing", "unavailable", "not provided"))
    })
    details = {
        "missingFiles": sorted(expected_files - found_files),
        "missingBacklogIds": sorted(expected_ids - found_ids),
        "unexpectedFiles": sorted(found_files - expected_files),
        "unexpectedBacklogIds": sorted(found_ids - expected_ids),
        "duplicateFiles": duplicates(files),
        "duplicateBacklogIds": duplicates(ids),
        "invalidDispositionIds": invalid_dispositions,
    }
    valid = not any(details.values())
    return {
        "required": True, "valid": valid,
        "status": "covered_unverified" if valid else "incomplete",
        "expectedFileCount": len(expected_files),
        "observedFileCount": len(found_files),
        "expectedBacklogIdCount": len(expected_ids),
        "observedBacklogIdCount": len(found_ids),
        **details,
        "sourceManifestDigest": hashlib.sha256(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
