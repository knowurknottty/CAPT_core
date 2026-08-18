"""Deterministic VSA/SME-inspired structural analogy advisory engine."""

from __future__ import annotations

import hashlib
import math
import random
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from capt_lab.contracts import LabEngineRequest, LabEngineResult, LabInputError

_ENGINE_ID = "lab.analogy"
_ENGINE_VERSION = "0.1.0"
_DEFAULT_DIMS = 512
_MAX_DIMS = 4096
_MAX_ROLES = 64
_MAX_STRUCTURES = 64
_MAX_TEXT = 256
_ANALOGY_THRESHOLD = 0.3


def _finite_unit_vector(values: Sequence[float]) -> List[float]:
    norm = math.sqrt(sum(v * v for v in values))
    if not math.isfinite(norm) or norm <= 1e-15:
        raise LabInputError("vector norm is not finite and positive")
    return [v / norm for v in values]


def stable_symbol_vector(symbol: str, dims: int = _DEFAULT_DIMS) -> List[float]:
    if not isinstance(symbol, str) or not symbol or len(symbol) > _MAX_TEXT:
        raise LabInputError("symbol must be a non-empty string <= %d chars" % _MAX_TEXT)
    if isinstance(dims, bool) or not isinstance(dims, int) or dims < 16 or dims > _MAX_DIMS:
        raise LabInputError("dims must be an integer in [16, %d]" % _MAX_DIMS)
    digest = hashlib.sha256(symbol.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:16], "big", signed=False)
    rng = random.Random(seed)
    return _finite_unit_vector([rng.gauss(0.0, 1.0) for _ in range(dims)])


def _bind(a: Sequence[float], b: Sequence[float]) -> List[float]:
    return [x * y for x, y in zip(a, b)]


def _bundle(vectors: Iterable[Sequence[float]], dims: int) -> List[float]:
    items = list(vectors)
    if not items:
        return [0.0] * dims
    summed = [0.0] * dims
    for vector in items:
        if len(vector) != dims:
            raise LabInputError("vector dimensionality mismatch")
        for i, value in enumerate(vector):
            summed[i] += value
    norm = math.sqrt(sum(v * v for v in summed))
    if norm <= 1e-15:
        return [0.0] * dims
    return [v / norm for v in summed]


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise LabInputError("vector dimensionality mismatch")
    na = math.sqrt(sum(v * v for v in a))
    nb = math.sqrt(sum(v * v for v in b))
    if na <= 1e-15 or nb <= 1e-15:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


def _exact_fields(value: Mapping[str, Any], expected: Iterable[str], label: str) -> None:
    expected_set = set(expected)
    missing = expected_set - set(value)
    unknown = set(value) - expected_set
    if missing:
        raise LabInputError("%s missing field(s): %s" % (label, ", ".join(sorted(missing))))
    if unknown:
        raise LabInputError("%s unknown field(s): %s" % (label, ", ".join(sorted(unknown))))


def _bounded_text(label: str, value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > _MAX_TEXT:
        raise LabInputError("%s must be a non-empty string <= %d chars" % (label, _MAX_TEXT))
    return value


def _parse_structure(raw: Any, label: str) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise LabInputError("%s must be an object" % label)
    _exact_fields(raw, ("name", "roles"), label)
    name = _bounded_text(label + ".name", raw["name"])
    roles = raw["roles"]
    if not isinstance(roles, dict) or not 1 <= len(roles) <= _MAX_ROLES:
        raise LabInputError("%s.roles must contain 1..%d entries" % (label, _MAX_ROLES))
    parsed: Dict[str, str] = {}
    for role, filler in roles.items():
        role_s = _bounded_text(label + ".roles role", role)
        filler_s = _bounded_text(label + ".roles filler", filler)
        parsed[role_s] = filler_s
    return {"name": name, "roles": parsed}


def _encode_structure(structure: Mapping[str, Any], dims: int) -> Tuple[List[float], List[float]]:
    bindings: List[List[float]] = []
    role_vectors: List[List[float]] = []
    for role in sorted(structure["roles"]):
        filler = structure["roles"][role]
        role_vec = stable_symbol_vector("__role__" + role, dims)
        filler_vec = stable_symbol_vector(filler, dims)
        role_vectors.append(role_vec)
        bindings.append(_bind(role_vec, filler_vec))
    return _bundle(bindings, dims), _bundle(role_vectors, dims)


def _structural_map(value: Mapping[str, Any]) -> LabEngineResult:
    _exact_fields(value, ("source", "target"), "structural_map input")
    source = _parse_structure(value["source"], "source")
    target = _parse_structure(value["target"], "target")
    src_surface, src_skeleton = _encode_structure(source, _DEFAULT_DIMS)
    tgt_surface, tgt_skeleton = _encode_structure(target, _DEFAULT_DIMS)
    surface = _cosine(src_surface, tgt_surface)
    structural = _cosine(src_skeleton, tgt_skeleton)

    src_roles = set(source["roles"])
    tgt_roles = set(target["roles"])
    common = sorted(src_roles & tgt_roles)
    role_mapping: Dict[str, str] = {role: role for role in common}
    remaining_targets = set(tgt_roles - set(common))
    for src_role in sorted(src_roles - set(common)):
        src_vec = stable_symbol_vector("__role__" + src_role, _DEFAULT_DIMS)
        scored = [
            (_cosine(src_vec, stable_symbol_vector("__role__" + tgt_role, _DEFAULT_DIMS)), tgt_role)
            for tgt_role in sorted(remaining_targets)
        ]
        if scored:
            _, best = max(scored, key=lambda item: (item[0], item[1]))
            role_mapping[src_role] = best
            remaining_targets.remove(best)

    mapped_fillers = {
        source["roles"][src_role]: target["roles"][tgt_role]
        for src_role, tgt_role in sorted(role_mapping.items())
    }
    confidence = 0.7 * structural + 0.3 * surface
    return LabEngineResult(
        engine_id=_ENGINE_ID,
        engine_version=_ENGINE_VERSION,
        operation="structural_map",
        epistemic_class="heuristic",
        observation={
            "sourceName": source["name"],
            "targetName": target["name"],
            "structuralSimilarity": structural,
            "surfaceSimilarity": surface,
            "roleMapping": role_mapping,
            "mappedFillers": mapped_fillers,
            "confidence": confidence,
            "isAnalogy": structural >= _ANALOGY_THRESHOLD,
            "dimensions": _DEFAULT_DIMS,
        },
        limitations=(
            "VSA/SME alignment is an approximate structural heuristic, not proof of causal or semantic equivalence.",
            "Symbol vectors are SHA-256-seeded for reproducibility; numerical similarity still reflects the adopted embedding method.",
        ),
    )


def _schema_abstract(value: Mapping[str, Any]) -> LabEngineResult:
    _exact_fields(value, ("structures",), "schema_abstract input")
    raw = value["structures"]
    if not isinstance(raw, list) or not 2 <= len(raw) <= _MAX_STRUCTURES:
        raise LabInputError("structures must contain 2..%d entries" % _MAX_STRUCTURES)
    structures = [_parse_structure(item, "structures[%d]" % i) for i, item in enumerate(raw)]
    common_roles = set(structures[0]["roles"])
    counts: Dict[str, int] = {}
    for structure in structures:
        common_roles &= set(structure["roles"])
        for role in structure["roles"]:
            counts[role] = counts.get(role, 0) + 1
    coverage = {role: counts[role] / len(structures) for role in sorted(counts)}
    return LabEngineResult(
        engine_id=_ENGINE_ID,
        engine_version=_ENGINE_VERSION,
        operation="schema_abstract",
        epistemic_class="advisory",
        observation={
            "structureCount": len(structures),
            "commonRoles": sorted(common_roles),
            "roleCoverage": coverage,
        },
        limitations=(
            "Schema abstraction reports structural recurrence in supplied examples only.",
            "It does not establish generality, causality, correctness, or verification of the inferred schema.",
        ),
    )


def execute_analogy(request: LabEngineRequest, context: Mapping[str, Any]) -> LabEngineResult:
    if request.engine_id != _ENGINE_ID:
        raise LabInputError("analogy adapter received wrong engineId")
    if request.operation == "structural_map":
        return _structural_map(request.input)
    if request.operation == "schema_abstract":
        return _schema_abstract(request.input)
    raise LabInputError("unsupported analogy operation %s" % request.operation)
