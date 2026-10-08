"""Machine validation for approval-bound deep Vessel Charter output."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional

from .cohort_contract import normalize_cohort_spec

_VESSEL_ROW = re.compile(
    r"^CAPT_VESSEL\s+(?P<id>[A-Za-z0-9._:-]+-v\d{4})\s*\|\s*(?P<body>.+)$"
)
_CANDIDATE_ROW = re.compile(
    r"^CAPT_CANDIDATE\s+(?P<id>C(?:N)?\d{4})\s*\|\s*(?P<body>.+)$"
)
_AUDIT = re.compile(r"^CAPT_CHARTER_AUDIT\s*\|\s*(?P<body>.+)$")
_INCOMPLETE = re.compile(r"^CAPT_COHORT_INCOMPLETE(?:\s|$)", re.I)
_TOKEN = re.compile(r"[a-z0-9][a-z0-9_+.-]{2,}", re.I)
_VESSEL_COMPARE_FIELDS = ("WHAT", "WHY", "HOW", "AGAINST", "FALSIFIER", "DELTA")
_CANDIDATE_COMPARE_FIELDS = ("AXIS", "MECH", "FALSIFIER", "DELTA")
_FIELD_ALIASES = {"MESH": "MECH"}
_STOP = frozenset({
    "the","and","for","with","from","that","this","into","using","use","used","other",
    "vessel","cohort","test","method","evidence","decision","change","analysis","model",
    "should","would","could","must","against","known","current","task","problem",
})


def _strict_policy(spec: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    normalized = normalize_cohort_spec(spec)
    if normalized is None:
        return None
    policy = normalized.get("vesselCharterPolicy")
    if not policy or not bool(policy.get("strictLedger", False)):
        return None
    return normalized


def expected_vessel_ids(spec: Dict[str, Any]) -> tuple[str, ...]:
    normalized = normalize_cohort_spec(spec)
    if normalized is None:
        return ()
    cohort_id = str(normalized["cohortId"])
    count = int(normalized["vesselsPerCohort"])
    return tuple(f"{cohort_id}-v{i:04d}" for i in range(1, count + 1))


def expected_candidate_minimum(spec: Dict[str, Any]) -> int:
    normalized = normalize_cohort_spec(spec)
    if normalized is None:
        return 0
    policy = normalized.get("vesselCharterPolicy") or {}
    return int(normalized["vesselsPerCohort"]) * int(policy.get("candidateMultiplier", 0))


def _parse_fields_with_lint(
    body: str,
    *,
    known_fields: tuple[str, ...] = (),
) -> tuple[Dict[str, str], list[str]]:
    """Parse charter fields while separating semantic content from format lint.

    Canonical syntax is KEY=value. Providers sometimes emit KEY:value,
    KEY>value, or unambiguous split form KEY|value. These variants retain
    semantic content and are reported as lint instead of false missing fields.
    """
    fields: Dict[str, str] = {}
    lint: list[str] = []
    known = {str(x).upper() for x in known_fields}
    parts = [part.strip() for part in str(body or "").split("|")]
    i = 0
    while i < len(parts):
        token = parts[i]
        parsed = False
        for sep in ("=", ":", ">"):
            if sep not in token:
                continue
            raw_key, value = token.split(sep, 1)
            raw_key = raw_key.strip().upper()
            key = raw_key
            if known and key not in known:
                key = _FIELD_ALIASES.get(raw_key, "")
                if not key or key not in known:
                    continue
                lint.append(f"{key}:field-alias:{raw_key}")
            fields[key] = value.strip()
            if sep != "=":
                lint.append(f"{key}:noncanonical-separator:{sep}")
            parsed = True
            break
        if parsed:
            i += 1
            continue

        raw_key = token.strip().upper()
        key = raw_key
        alias_used = False
        if known and key not in known:
            key = _FIELD_ALIASES.get(raw_key, "")
            alias_used = bool(key and key in known)
        if key in known and i + 1 < len(parts):
            nxt = parts[i + 1].strip()
            next_is_keyed = any(
                nxt.upper() == candidate
                or nxt.upper().startswith(candidate + "=")
                or nxt.upper().startswith(candidate + ":")
                or nxt.upper().startswith(candidate + ">")
                for candidate in known
            )
            if nxt and not next_is_keyed:
                fields[key] = nxt
                if alias_used:
                    lint.append(f"{key}:field-alias:{raw_key}")
                lint.append(f"{key}:split-pipe-value")
                i += 2
                continue
        i += 1
    return fields, lint


def _parse_fields(body: str) -> Dict[str, str]:
    fields, _ = _parse_fields_with_lint(body)
    return fields


def _parse_int_fields(body: str) -> Dict[str, int]:
    raw = _parse_fields(body)
    out: Dict[str, int] = {}
    for key, value in raw.items():
        if re.fullmatch(r"-?\d+", value):
            out[key.lower()] = int(value)
    return out


def _word_count(fields: Dict[str, str]) -> int:
    return sum(len(re.findall(r"\b\w+\b", str(value))) for value in fields.values())


def _tokens(fields: Dict[str, str], compare_fields: tuple[str, ...]) -> frozenset[str]:
    joined = " ".join(fields.get(name, "") for name in compare_fields).lower()
    return frozenset(
        token for token in _TOKEN.findall(joined)
        if token not in _STOP and not token.isdigit()
    )


def _similarity(left: frozenset[str], right: frozenset[str]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    return (len(left & right) / len(union)) if union else 0.0


def _orthogonality(
    observed: Dict[str, Dict[str, str]],
    *,
    compare_fields: tuple[str, ...],
) -> Dict[str, Any]:
    ids = sorted(observed)
    toks = {
        item_id: _tokens(observed[item_id], compare_fields)
        for item_id in ids
    }
    hard_pairs: list[Dict[str, Any]] = []
    warning_pairs: list[Dict[str, Any]] = []
    maxima: list[float] = []
    max_similarity = 0.0
    for i, left in enumerate(ids):
        local_max = 0.0
        for right in ids[i + 1:]:
            score = _similarity(toks[left], toks[right])
            local_max = max(local_max, score)
            max_similarity = max(max_similarity, score)
            if score >= 0.90:
                hard_pairs.append({
                    "left": left, "right": right, "similarity": round(score, 4)
                })
            elif score >= 0.72:
                warning_pairs.append({
                    "left": left, "right": right, "similarity": round(score, 4)
                })
        maxima.append(local_max)
    mean_max = (sum(maxima) / len(maxima)) if maxima else 0.0
    return {
        "maxPairwiseSimilarity": round(max_similarity, 4),
        "meanForwardMaxSimilarity": round(mean_max, 4),
        "hardDuplicatePairs": hard_pairs,
        "redundancyWarnings": warning_pairs[:50],
        "orthogonalityScore": round(1.0 - mean_max, 4),
    }


def _validate_legacy(
    text: str,
    normalized: Dict[str, Any],
    policy: Dict[str, Any],
) -> Dict[str, Any]:
    required_fields = tuple(str(x).upper() for x in policy["requiredFields"])
    expected = expected_vessel_ids(normalized)
    expected_set = set(expected)
    observed: Dict[str, Dict[str, str]] = {}
    duplicates: list[str] = []
    unexpected: list[str] = []
    malformed: list[str] = []
    missing_fields: Dict[str, list[str]] = {}
    audit_rows: list[Dict[str, int]] = []

    for line in str(text or "").splitlines():
        stripped = line.strip()
        audit_match = _AUDIT.match(stripped)
        if audit_match is not None:
            audit_rows.append(_parse_int_fields(audit_match.group("body")))
            continue
        if not stripped.startswith("CAPT_VESSEL "):
            continue
        match = _VESSEL_ROW.match(stripped)
        if match is None:
            malformed.append(stripped[:240])
            continue
        vessel_id = match.group("id")
        if vessel_id in observed:
            duplicates.append(vessel_id)
            continue
        if vessel_id not in expected_set:
            unexpected.append(vessel_id)
        fields = _parse_fields(match.group("body"))
        observed[vessel_id] = fields
        missing = [name for name in required_fields if not fields.get(name, "").strip()]
        if missing:
            missing_fields[vessel_id] = missing

    missing_ids = [vessel_id for vessel_id in expected if vessel_id not in observed]
    audit = audit_rows[0] if len(audit_rows) == 1 else {}
    expected_candidates = expected_candidate_minimum(normalized)
    audit_valid = (
        len(audit_rows) == 1
        and audit.get("generated", -1) >= expected_candidates
        and audit.get("selected", -1) == len(expected)
        and audit.get("expansion_rounds", -1) >= 0
        and audit.get("deduplicated", -1) >= 0
    )
    ortho = _orthogonality(observed, compare_fields=_VESSEL_COMPARE_FIELDS)
    valid = not (
        missing_ids or duplicates or unexpected or malformed or missing_fields
        or not audit_valid or bool(ortho["hardDuplicatePairs"])
    )
    return {
        "required": True,
        "schemaVersion": "1.0.0",
        "valid": valid,
        "status": "complete" if valid else "incomplete",
        "cohortId": normalized["cohortId"],
        "expectedCount": len(expected),
        "observedCount": len(observed),
        "expectedCandidateCount": expected_candidates,
        "charterAudit": audit,
        "charterAuditRowCount": len(audit_rows),
        "charterAuditValid": audit_valid,
        "missingVesselIds": missing_ids,
        "duplicateVesselIds": sorted(set(duplicates)),
        "unexpectedVesselIds": sorted(set(unexpected)),
        "malformedRows": malformed,
        "missingFields": missing_fields,
        "orthogonality": ortho,
        "incompleteMarkerPresent": bool(_INCOMPLETE.search(str(text or ""))),
    }


def _validate_v2(
    text: str,
    normalized: Dict[str, Any],
    policy: Dict[str, Any],
) -> Dict[str, Any]:
    required_fields = tuple(str(x).upper() for x in policy["requiredFields"])
    candidate_required = tuple(
        str(x).upper() for x in policy["candidateRequiredFields"]
    )
    expected = expected_vessel_ids(normalized)
    expected_set = set(expected)
    expected_candidates = expected_candidate_minimum(normalized)

    vessels: Dict[str, Dict[str, str]] = {}
    candidates: Dict[str, Dict[str, str]] = {}
    vessel_duplicates: list[str] = []
    candidate_duplicates: list[str] = []
    unexpected_vessels: list[str] = []
    malformed: list[str] = []
    vessel_missing_fields: Dict[str, list[str]] = {}
    candidate_missing_fields: Dict[str, list[str]] = {}
    candidate_overlong: Dict[str, int] = {}
    format_lint: Dict[str, list[str]] = {}
    audit_rows: list[Dict[str, int]] = []
    incomplete_marker = False

    for line in str(text or "").splitlines():
        stripped = line.strip()
        if _INCOMPLETE.match(stripped):
            incomplete_marker = True
            continue

        audit_match = _AUDIT.match(stripped)
        if audit_match is not None:
            audit_rows.append(_parse_int_fields(audit_match.group("body")))
            continue

        if stripped.startswith("CAPT_CANDIDATE "):
            match = _CANDIDATE_ROW.match(stripped)
            if match is None:
                malformed.append(stripped[:240])
                continue
            raw_candidate_id = match.group("id").upper()
            candidate_id = raw_candidate_id
            id_lint: list[str] = []
            if raw_candidate_id.startswith("CN"):
                candidate_id = "C" + raw_candidate_id[2:]
                id_lint.append("candidate_id_alias:CN->C")
            if candidate_id in candidates:
                candidate_duplicates.append(candidate_id)
                continue
            fields, row_lint = _parse_fields_with_lint(
                match.group("body"), known_fields=candidate_required
            )
            row_lint = id_lint + row_lint
            candidates[candidate_id] = fields
            if row_lint:
                format_lint[candidate_id] = row_lint
            missing = [
                name for name in candidate_required
                if not fields.get(name, "").strip()
            ]
            if missing:
                candidate_missing_fields[candidate_id] = missing
            words = _word_count({
                name: fields.get(name, "") for name in candidate_required
            })
            if words > int(policy["candidateMaxWords"]):
                candidate_overlong[candidate_id] = words
            continue

        if stripped.startswith("CAPT_VESSEL "):
            match = _VESSEL_ROW.match(stripped)
            if match is None:
                malformed.append(stripped[:240])
                continue
            vessel_id = match.group("id")
            if vessel_id in vessels:
                vessel_duplicates.append(vessel_id)
                continue
            if vessel_id not in expected_set:
                unexpected_vessels.append(vessel_id)
            fields, row_lint = _parse_fields_with_lint(
                match.group("body"), known_fields=required_fields
            )
            vessels[vessel_id] = fields
            if row_lint:
                format_lint[vessel_id] = row_lint
            missing = [
                name for name in required_fields
                if not fields.get(name, "").strip()
            ]
            if missing:
                vessel_missing_fields[vessel_id] = missing

    missing_vessel_ids = [
        vessel_id for vessel_id in expected if vessel_id not in vessels
    ]
    audit = audit_rows[0] if len(audit_rows) == 1 else {}

    candidate_count_valid = len(candidates) >= expected_candidates
    audit_valid = (
        len(audit_rows) == 1
        and audit.get("candidates", -1) == len(candidates)
        and audit.get("selected", -1) == len(vessels) == len(expected)
        and audit.get("expansion_rounds", -1) >= 0
    )

    selected_sources: Dict[str, str] = {}
    missing_sources: list[str] = []
    duplicate_sources: list[str] = []
    seen_sources: set[str] = set()
    for vessel_id, fields in vessels.items():
        source = fields.get("SOURCE", "").strip().upper()
        if re.fullmatch(r"CN\d{4}", source):
            source = "C" + source[2:]
            format_lint.setdefault(vessel_id, []).append(
                "source_candidate_id_alias:CN->C"
            )
        if not source or source not in candidates:
            missing_sources.append(vessel_id)
            continue
        selected_sources[vessel_id] = source
        if source in seen_sources:
            duplicate_sources.append(source)
        seen_sources.add(source)

    candidate_ortho = _orthogonality(
        candidates, compare_fields=_CANDIDATE_COMPARE_FIELDS
    )
    vessel_ortho = _orthogonality(
        vessels, compare_fields=_VESSEL_COMPARE_FIELDS
    )

    valid = not (
        incomplete_marker
        or missing_vessel_ids
        or vessel_duplicates
        or candidate_duplicates
        or unexpected_vessels
        or malformed
        or vessel_missing_fields
        or candidate_missing_fields
        or candidate_overlong
        or not candidate_count_valid
        or not audit_valid
        or missing_sources
        or duplicate_sources
        or bool(candidate_ortho["hardDuplicatePairs"])
        or bool(vessel_ortho["hardDuplicatePairs"])
    )

    return {
        "required": True,
        "schemaVersion": "2.0.0",
        "valid": valid,
        "status": "complete" if valid else "incomplete",
        "cohortId": normalized["cohortId"],
        "expectedCount": len(expected),
        "observedCount": len(vessels),
        "expectedCandidateCount": expected_candidates,
        "observedCandidateCount": len(candidates),
        "candidateCountValid": candidate_count_valid,
        "charterAudit": audit,
        "charterAuditRowCount": len(audit_rows),
        "charterAuditValid": audit_valid,
        "missingVesselIds": missing_vessel_ids,
        "duplicateVesselIds": sorted(set(vessel_duplicates)),
        "unexpectedVesselIds": sorted(set(unexpected_vessels)),
        "duplicateCandidateIds": sorted(set(candidate_duplicates)),
        "malformedRows": malformed,
        "missingFields": vessel_missing_fields,
        "candidateMissingFields": candidate_missing_fields,
        "candidateOverlong": candidate_overlong,
        "formatLint": format_lint,
        "formatLintCount": sum(len(v) for v in format_lint.values()),
        "selectedSources": selected_sources,
        "missingSourceVessels": sorted(set(missing_sources)),
        "duplicateSelectedSources": sorted(set(duplicate_sources)),
        "candidateOrthogonality": candidate_ortho,
        "orthogonality": vessel_ortho,
        "incompleteMarkerPresent": incomplete_marker,
    }


def validate_vessel_text(
    text: str,
    spec: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    normalized = _strict_policy(spec)
    if normalized is None:
        return {"required": False, "valid": True, "status": "not_required"}

    policy = normalized["vesselCharterPolicy"]
    if str(policy.get("schemaVersion")) == "2.0.0":
        return _validate_v2(text, normalized, policy)
    return _validate_legacy(text, normalized, policy)


def validate_vessel_artifact(
    artifact_path: str | Path,
    spec: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    path = Path(artifact_path)
    if _strict_policy(spec) is None:
        return validate_vessel_text("", spec)
    if not path.exists():
        return {
            "required": True,
            "valid": False,
            "status": "incomplete",
            "artifactMissing": True,
            "artifactPath": str(path),
        }
    result = validate_vessel_text(path.read_text(errors="replace"), spec)
    result["artifactPath"] = str(path)
    return result
