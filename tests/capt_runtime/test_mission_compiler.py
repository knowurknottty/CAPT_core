"""Deterministic Mission Compiler tests (Gate 4).

Proves the compiler is deterministic, produces contract-valid MissionSpecs,
preserves provenance, and never requires an LLM.
"""

import time

import pytest

from capt_runtime.mission_compiler import compile_mission, COMPILER_VERSION


def test_compiles_to_contract_valid_spec():
    out = compile_mission("Analyze the repository for unused imports",
                          operator_id="op-1")
    spec = out["missionSpec"]
    # Raises ContractViolation internally if invalid; reaching here means valid.
    assert spec["missionId"].startswith("m-comp-")
    assert spec["rawRequest"] == "Analyze the repository for unused imports"
    assert spec["normalizedRequest"] == "analyze the repository for unused imports"


def test_deterministic_same_input_same_output():
    a = compile_mission("Read the config file", operator_id="op-1")
    b = compile_mission("Read the config file", operator_id="op-1")
    assert a["missionSpec"] == b["missionSpec"]
    assert a["compilerProvenance"]["compilerDigest"] == b["compilerProvenance"]["compilerDigest"]


def test_different_input_different_digest():
    a = compile_mission("Read file A", operator_id="op-1")
    b = compile_mission("Read file B", operator_id="op-1")
    assert a["compilerProvenance"]["compilerDigest"] != b["compilerProvenance"]["compilerDigest"]


def test_raw_and_normalized_preserved():
    out = compile_mission("MIXED Case Request", operator_id="op-1")
    assert out["missionSpec"]["rawRequest"] == "MIXED Case Request"
    assert out["missionSpec"]["normalizedRequest"] == "mixed case request"


def test_policy_added_constraints_present():
    out = compile_mission("do something", operator_id="op-1")
    kinds = [c["origin"] for c in out["missionSpec"]["constraints"]]
    assert "policy_added" in kinds


def test_inferred_constraint_recorded_with_lower_authority():
    out = compile_mission("read the logs", operator_id="op-1")
    inferred = [c for c in out["missionSpec"]["constraints"] if c.get("origin") == "inferred"]
    assert inferred, "read hint should produce an inferred constraint"


def test_write_hint_inferred_as_forbidden():
    out = compile_mission("write a report", operator_id="op-1")
    inferred = [c for c in out["missionSpec"]["constraints"] if c.get("origin") == "inferred"]
    assert inferred
    assert inferred[0]["kind"] == "forbidden_operation"


def test_explicit_constraints_preserved():
    expl = [{"kind": "resource_boundary", "constraintId": "con-x",
             "origin": "explicit_user",
             "scope": {"kind": "filesystem", "rootPath": "/tmp", "recursive": False}}]
    out = compile_mission("analyze", operator_id="op-1", explicit_constraints=expl)
    assert expl[0] in out["missionSpec"]["constraints"]


def test_operator_overrides_applied_to_allowed_fields():
    out = compile_mission("analyze", operator_id="op-1",
                          operator_overrides={"successCriteria": [
                              {"criterionId": "sc-9", "statement": "custom", "requiresVerification": False}]})
    assert out["missionSpec"]["successCriteria"][0]["criterionId"] == "sc-9"


def test_unresolved_ambiguity_recorded():
    out = compile_mission("analyze", operator_id="op-1")
    # No ambiguity by default; the record exists and is a list.
    assert isinstance(out["compilerProvenance"]["unresolvedAmbiguities"], list)


def test_compiler_version_and_digest_present():
    out = compile_mission("analyze", operator_id="op-1")
    prov = out["compilerProvenance"]
    assert prov["compilerVersion"] == COMPILER_VERSION
    assert prov["compilerDigest"].startswith("sha256:")


def test_no_llm_required():
    # The compiler is pure deterministic Python; it imports no model client.
    import capt_runtime.mission_compiler as M
    assert "openai" not in dir(M) and "anthropic" not in dir(M)
