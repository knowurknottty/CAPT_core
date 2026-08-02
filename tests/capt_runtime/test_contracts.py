"""Conformance tests: contract schema, generation, and cross-language parity."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CONTRACTS = REPO / "contracts"
GEN_PY = CONTRACTS / "generated" / "python"
GEN_TS = CONTRACTS / "generated" / "typescript"

sys.path.insert(0, str(GEN_PY))

import capt_contracts  # noqa: E402


def test_schema_is_single_source():
    """I1: JSON Schema files are the only normative source."""
    schemas = sorted(CONTRACTS.glob("schema/*.schema.json"))
    assert schemas, "no schema files"
    # The generator reads only these; confirm the generator imports them.
    from contracts.tools import schema_model  # type: ignore

    model = schema_model.SchemaModel()
    assert model.types, "generator produced no types from schema"


def test_generation_reproducible():
    """I2: two generations into separate dirs are byte-identical."""
    import tempfile

    a = Path(tempfile.mkdtemp()) / "a"
    b = Path(tempfile.mkdtemp()) / "b"
    subprocess.run([sys.executable, "contracts/tools/generate.py", "--out", str(a)],
                  cwd=REPO, check=True)
    subprocess.run([sys.executable, "contracts/tools/generate.py", "--out", str(b)],
                  cwd=REPO, check=True)
    diff = subprocess.run(["diff", "-r", str(a), str(b)], capture_output=True, text=True)
    assert diff.returncode == 0, diff.stdout + diff.stderr


def test_drift_check_clean():
    """CI-equivalent drift gate passes on the committed bindings."""
    result = subprocess.run([sys.executable, "contracts/tools/check_drift.py"],
                            cwd=REPO, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_cross_language_fixture_parity():
    """Both languages validate every fixture identically, including error text."""
    # Python side
    py_results = {}
    for fx in sorted(CONTRACTS.glob("fixtures/*.json")):
        data = json.loads(fx.read_text())
        for case in data["cases"]:
            errs = capt_contracts.validate(case["type"], case["value"])
            py_results[case["id"]] = errs

    # TypeScript side — parse the LAST stdout line as JSON (prior lines are
    # human-readable progress).
    ts_result = subprocess.run(
        ["node", str(REPO / "contracts/tools/ts_parity.mjs")],
        cwd=REPO, capture_output=True, text=True,
    )
    assert ts_result.returncode == 0, ts_result.stdout + ts_result.stderr
    ts_payload = json.loads(ts_result.stdout.strip().splitlines()[-1])
    assert ts_payload["failures"] == 0, ts_payload

    # Cross-check that Python and TS agree on each case's error list.
    for case_id, py_errs in py_results.items():
        ts_case = next(c for c in ts_payload["cases"] if c["id"] == case_id)
        assert py_errs == ts_case["errors"], (case_id, py_errs, ts_case["errors"])


def test_invalid_discriminant_rejected():
    from capt_contracts import validate

    errs = validate("Constraint", {"kind": "wormhole", "constraintId": "x"})
    assert any("invalid discriminant" in e for e in errs)


def test_missing_required_field_rejected():
    from capt_contracts import validate

    errs = validate("MissionSpec", {"missionId": "m1"})  # missing rawRequest etc.
    assert errs, "missing required fields should fail"


def test_version_visible_in_both_languages():
    assert capt_contracts.CONTRACT_SCHEMA_VERSION == "1.0.0"
    version_ts = (GEN_TS / "src" / "version.ts").read_text()
    assert "1.0.0" in version_ts
