"""Deterministic Mission Compiler (ADR-DT-PLANE-CONV, Gate 4).

An explicit, deterministic boundary between raw operator intent and cognition.

    raw request
    -> deterministic parsing and validation
    -> current policy and known constraints
    -> MissionSpec
    -> unresolved ambiguity record
    -> cognition and planning

The compiler NEVER invokes an LLM. Transformations that can be deterministic are
deterministic. LLM assistance may only PROPOSE interpretation when ambiguity
remains, and must not silently mutate the MissionSpec.

The compiler preserves:
- raw request
- normalized request
- explicit constraints
- inferred constraints
- policy-added constraints
- current-state assumptions
- operator overrides
- unresolved ambiguities
- provenance
- compiler version and digest
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional

from .contracts import CONTRACT_SCHEMA_VERSION, canonical_json, digest, require

COMPILER_VERSION = "1.0.0"

# Known policy constraints applied by the runtime (policy-added).
DEFAULT_POLICY_CONSTRAINTS: List[Dict[str, Any]] = [
    {
        "kind": "forbidden_operation",
        "constraintId": "pol-no-write",
        "origin": "policy_added",
        "operations": ["repository.write", "filesystem.write", "git.commit", "git.push"],
    },
]

_WRITE_HINT_RE = re.compile(r"\b(write|commit|push|mutate|deploy|install|delete|remove)\b", re.IGNORECASE)
_READ_HINT_RE = re.compile(r"\b(read|analy|inspect|review|examine|list|show|find)\b", re.IGNORECASE)


def _normalize(raw: str) -> str:
    return raw.strip().lower()


def _inferred_constraint(raw_norm: str) -> Optional[Dict[str, Any]]:
    """Deterministic inference of a read-only posture from the normalized request.

    This is INFERENCE, recorded with origin='inferred' and lower authority. It is
    never silently promoted to an explicit constraint.
    """
    if _WRITE_HINT_RE.search(raw_norm):
        return {
            "kind": "forbidden_operation",
            "constraintId": "inf-no-write",
            "origin": "inferred",
            "operations": ["repository.write", "filesystem.write", "git.commit", "git.push"],
        }
    if _READ_HINT_RE.search(raw_norm):
        return {
            "kind": "resource_boundary",
            "constraintId": "inf-read-only",
            "origin": "inferred",
            "scope": {"kind": "filesystem", "rootPath": "/tmp", "recursive": False},
        }
    return None


def compile_mission(
    raw_request: str,
    *,
    operator_id: str,
    explicit_constraints: Optional[List[Dict[str, Any]]] = None,
    operator_overrides: Optional[Dict[str, Any]] = None,
    current_state_assumptions: Optional[List[str]] = None,
    mission_id: Optional[str] = None,
    success_statement: str = "mission objective achieved and verified",
    termination_statement: str = "mission halted by operator or failure",
    compiler_version: str = COMPILER_VERSION,
) -> Dict[str, Any]:
    """Deterministically compile a raw request into a contract-valid MissionSpec.

    Returns the MissionSpec plus a compiler provenance record. The MissionSpec
    is validated against the contract before being returned.
    """
    raw = (raw_request or "").strip()
    if not raw:
        raise ValueError("raw request is required")

    normalized = _normalize(raw)
    explicit = list(explicit_constraints or [])
    inferred = _inferred_constraint(normalized)
    inferred_list = [inferred] if inferred else []
    policy = DEFAULT_POLICY_CONSTRAINTS

    objectives = [{
        "objectiveId": "obj-1",
        "statement": raw,
        "priority": 1,
    }]
    success_criteria = [{
        "criterionId": "sc-1",
        "statement": success_statement,
        "requiresVerification": True,
    }]
    termination_criteria = "tc-1"
    termination = [{
        "criterionId": termination_criteria,
        "statement": termination_statement,
        "terminalState": "failed",
    }]

    mid = mission_id or ("m-comp-%s" % digest(raw + normalized)[:12])

    spec: Dict[str, Any] = {
        "schemaVersion": CONTRACT_SCHEMA_VERSION,
        "missionId": mid,
        "rawRequest": raw,
        "normalizedRequest": normalized,
        "objectives": objectives,
        "constraints": explicit + inferred_list + policy,
        "successCriteria": success_criteria,
        "terminationCriteria": termination,
        "unresolvedAmbiguities": [],
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # Operator overrides are recorded but only applied to allowed fields.
    overrides = operator_overrides or {}
    for key in ("successCriteria", "terminationCriteria", "objectives"):
        if key in overrides:
            spec[key] = overrides[key]

    # Validate the compiled spec against the contract (deterministic gate).
    require("MissionSpec", spec)

    provenance = {
        "compilerVersion": compiler_version,
        "compilerDigest": digest({"version": compiler_version, "spec": spec}),
        "rawRequest": raw,
        "normalizedRequest": normalized,
        "explicitConstraints": explicit,
        "inferredConstraints": inferred_list,
        "policyAddedConstraints": policy,
        "currentStateAssumptions": current_state_assumptions or [],
        "operatorOverrides": overrides,
        "unresolvedAmbiguities": spec["unresolvedAmbiguities"],
    }

    return {
        "schemaVersion": CONTRACT_SCHEMA_VERSION,
        "missionSpec": spec,
        "compilerProvenance": provenance,
    }
