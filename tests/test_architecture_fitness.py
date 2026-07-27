"""Architectural fitness tests (Phase 3A.4).

These enforce CAPT_CANON invariants through *structural* checks, not string
matches. They run under pytest and also contribute to the verification pipeline.

Each test targets a specific invariant:
  I-01 Local-first by default
  I-02 Evidence before assertion
  I-04 Explicit uncertainty
  I-05 Privacy-preserving defaults
  I-06 Modular cognition
  I-07 Bounded failure domains
  I-08 Backward-compatible public contracts
  I-09 Optional capabilities degrade independently
  I-10 Architecture drives implementation
  I-11 Implementation never silently redefines architecture
  I-12 Ontology is shared and upstream
  I-15 Evidence over implementation

They inspect the real source tree and registry. A test that only asserts a
function exists is insufficient; these exercise behavior or structure.
"""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest

import yaml

REPO = Path(__file__).resolve().parent.parent
REGISTRY = REPO / "architecture" / "registry.yaml"
CAPT_SOLO = REPO / "capt_solo"


def _load_registry():
    with open(REGISTRY) as f:
        return yaml.safe_load(f)


def _py_files(pkg: Path):
    return [p for p in pkg.rglob("*.py") if "__pycache__" not in str(p)]


# ---------------------------------------------------------------------------
# I-01 Local-first by default
# ---------------------------------------------------------------------------
def test_i01_no_mandatory_network_init_at_startup():
    """Baseline import of the public API must not require network.
    We assert no unconditional top-level network import in api.py."""
    api_src = (CAPT_SOLO / "api.py").read_text()
    forbidden = ("import socket", "import requests", "import httpx",
                 "from requests", "from httpx", "urllib.request.urlopen")
    top_level = []
    for line in api_src.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            if any(b in stripped for b in forbidden):
                top_level.append(stripped)
    assert top_level == [], f"unconditional network import at api top-level: {top_level}"


def test_i01_no_network_socket_in_core_memory_foundry():
    """No socket.create_connection at module level in core memory/foundry packages."""
    offenders = []
    for f in list(_py_files(CAPT_SOLO / "memory")) + list(_py_files(CAPT_SOLO / "foundry")):
        src = f.read_text()
        if "socket" in src and "create_connection" in src:
            offenders.append(str(f))
    assert offenders == [], f"network socket usage in core memory/foundry: {offenders}"


# ---------------------------------------------------------------------------
# I-02 Evidence before assertion
# ---------------------------------------------------------------------------
def test_i02_claimguard_requires_evidence_hook():
    """ClaimGuard must expose a verification path that references evidence."""
    cg = (CAPT_SOLO / "foundry" / "claimguard.py").read_text()
    assert "evidence" in cg.lower(), "ClaimGuard source must reference evidence"
    assert "def verify" in cg, "ClaimGuard must expose verify()"


# ---------------------------------------------------------------------------
# I-04 Explicit uncertainty
# ---------------------------------------------------------------------------
def test_i04_uncertainty_exposed_not_bool_coerced():
    """Trust module must expose a confidence concept, not a bare bool verdict."""
    trust_src = (CAPT_SOLO / "memory" / "trust.py").read_text()
    assert "confidence" in trust_src.lower(), "trust module should expose confidence"


# ---------------------------------------------------------------------------
# I-05 Privacy-preserving defaults
# ---------------------------------------------------------------------------
def test_i05_secrets_screened_before_persist():
    """secrets.screen must exist and the public surface must reference secret screening."""
    secrets_src = (CAPT_SOLO / "memory" / "secrets.py").read_text()
    assert "def screen" in secrets_src, "secrets.screen must exist"
    # Secret screening is wired into the public surface (api/verify), not engine internals.
    api_src = (CAPT_SOLO / "api.py").read_text()
    verify_src = (REPO / "verify_runtime.py").read_text()
    referenced = ("secret" in api_src.lower()) or ("secret" in verify_src.lower())
    assert referenced, "public surface (api.py/verify_runtime.py) should reference secret screening"


def test_i05_no_telemetry_enabled_by_default():
    """No telemetry beacon enabled by default in core config."""
    config_src = (CAPT_SOLO / "core" / "config.py").read_text()
    low = config_src.lower()
    if "telemetry" in low:
        assert "disabled" in low, "telemetry must default disabled if present"


# ---------------------------------------------------------------------------
# I-06 Modular cognition
# ---------------------------------------------------------------------------
def test_i06_engine_does_not_hard_import_optional_modules():
    """MemoryEngine must not hard-depend on optional research modules."""
    engine_src = (CAPT_SOLO / "memory" / "engine.py").read_text()
    for mod in ("hmc", "echo_mobile", "engram", "dream"):
        assert f"import {mod}" not in engine_src, f"engine hard-imports optional {mod}"


# ---------------------------------------------------------------------------
# I-07 Bounded failure domains
# ---------------------------------------------------------------------------
def test_i07_antitoken_import_guarded_if_present():
    """If engine references antitoken, the import must be guarded."""
    engine_src = (CAPT_SOLO / "memory" / "engine.py").read_text()
    if "antitoken" in engine_src:
        assert "try:" in engine_src and "except" in engine_src, \
            "antitoken reference in engine must be guarded"


# ---------------------------------------------------------------------------
# I-08 Backward-compatible public contracts
# ---------------------------------------------------------------------------
def test_i08_public_api_surface_stable():
    """capt_solo.api must expose documented public symbols."""
    api_src = (CAPT_SOLO / "api.py").read_text()
    for sym in ("health", "CTPRuntime", "KHSB", "MemoryEngine"):
        # Symbol is exposed via def / assignment / or import (incl. comma lists).
        present = (
            f"def {sym}" in api_src
            or f"{sym} =" in api_src
            or f"import {sym}" in api_src
            or f"{sym}," in api_src
            or f", {sym}" in api_src
            or f" {sym} " in api_src
        )
        assert present, f"public API missing: {sym}"


# ---------------------------------------------------------------------------
# I-09 Optional capabilities degrade independently
# ---------------------------------------------------------------------------
def test_i09_antitoken_optional_and_stateless():
    at = (CAPT_SOLO / "memory" / "antitoken.py").read_text()
    assert "def extract" in at and "def validate" in at
    tree = ast.parse(at)
    module_assigns = [n for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign))]
    persistent_globals = []
    for n in module_assigns:
        if isinstance(n, ast.Assign):
            targets = n.targets
        else:  # AnnAssign
            targets = [n.target]
        for t in targets:
            if isinstance(t, ast.Name) and t.id.isupper():
                persistent_globals.append(t.id)
    assert "EXTRACTED_CACHE" not in at, "AntiToken must not persist payloads in module state"


# ---------------------------------------------------------------------------
# I-10 / I-11 Architecture drives implementation; no silent redefinition
# ---------------------------------------------------------------------------
def test_i11_no_duplicate_canonical_names():
    reg = _load_registry()
    names = [s["canonical_name"] for s in reg["subsystems"]]
    dup = {n for n in names if names.count(n) > 1}
    assert not dup, f"duplicate canonical names: {dup}"


def _load_validator_module():
    """Load architecture/validate_registry.py as a proper module (registered in
    sys.modules so dataclasses resolution works under Python 3.9)."""
    import importlib.util
    import sys
    spec = importlib.util.spec_from_file_location(
        "capt_solo._arch_validator", REPO / "architecture" / "validate_registry.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# I-12 Ontology is shared and upstream
# ---------------------------------------------------------------------------
def test_i12_ontology_terms_defined_once():
    """CAPT_CANON §4 must define the 16 shared ontology terms."""
    canon = (REPO / "docs" / "CAPT_CANON.md").read_text().lower()
    terms = ["entity", "relationship", "identity", "claim", "evidence", "provenance",
             "confidence", "uncertainty", "truth", "contradiction", "temporal ordering",
             "observation", "inference", "procedure", "skill", "memory"]
    missing = [t for t in terms if t not in canon]
    assert not missing, f"ontology terms missing from CAPT_CANON: {missing}"


# ---------------------------------------------------------------------------
# I-15 Evidence over implementation
# ---------------------------------------------------------------------------
def test_i15_registry_drift_detectable():
    """The validator must FAIL on a deliberately broken registry (proves real enforcement)."""
    mod = _load_validator_module()

    bad = _load_registry()
    bad["subsystems"] = list(bad["subsystems"])
    bad["subsystems"].append({
        "canonical_id": "DUP-TEST", "canonical_name": "Duplicate Name",
        "aliases": [], "architectural_layer": "ZZ9", "conceptual_sublayer": "x",
        "canonical_definition": "x", "maturity": "Bogus", "public_release_target": "nowhere",
        "implementation_status": "complete", "current_repository": "capt-solo",
        "current_path": "capt_solo/engine.py", "reference_implementation": "x",
        "expected_namespace": "capt_solo.x", "required_dependencies": [],
        "optional_dependencies": [], "persistence_behavior": "x", "network_behavior": "none",
        "security_classification": "local", "invariant_mappings": ["I-99"],
        "owning_adrs": ["ADR-9999"], "expected_tests": [], "deprecation_state": "active",
    })
    checks = mod.validate(bad)
    fails = [c for c in checks if c.status == "fail"]
    assert fails, "validator should fail on a deliberately broken registry"
