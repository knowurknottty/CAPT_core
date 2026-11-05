"""Canonicalization conformance.

The critical test here is byte-identical agreement with
``capt_runtime.contracts``: the Foundry re-implements canonical_json/digest to
avoid a hard dependency on the generated bindings, and that duplication is only
safe if it is proven equal rather than assumed equal.
"""

from __future__ import annotations

import pytest

from capt_foundry import canonical as fc


def test_digest_form_matches_contract_pattern():
    assert fc.is_digest(fc.digest({"a": 1}))
    assert not fc.is_digest("sha256:XYZ")
    assert not fc.is_digest("deadbeef")


def test_canonical_json_is_key_order_independent():
    assert fc.canonical_json({"b": 1, "a": 2}) == fc.canonical_json({"a": 2, "b": 1})
    assert fc.digest({"b": 1, "a": 2}) == fc.digest({"a": 2, "b": 1})


def test_digest_is_sensitive_to_value_change():
    assert fc.digest({"a": 1}) != fc.digest({"a": 2})


def test_matches_capt_runtime_contracts_byte_for_byte():
    """Foundry canonicalization must equal the runtime's, or digests diverge."""
    runtime = pytest.importorskip("capt_runtime.contracts")
    samples = [
        {},
        {"a": 1},
        {"b": [1, 2, {"c": "d"}], "a": None},
        {"unicode": "Ada Lovelace — Analytical Engine ✓"},
        {"nested": {"deep": {"deeper": [True, False, 0.5]}}},
    ]
    for s in samples:
        assert fc.canonical_json(s) == runtime.canonical_json(s)
        assert fc.digest(s) == runtime.digest(s)


def test_rfc3339_validation():
    assert fc.is_rfc3339_z("2026-08-03T00:00:00Z")
    assert fc.is_rfc3339_z("2026-08-03T00:00:00.123Z")
    assert not fc.is_rfc3339_z("2026-08-03 00:00:00")
    assert not fc.is_rfc3339_z("2026-08-03T00:00:00+02:00")


def test_utc_now_is_valid_rfc3339():
    assert fc.is_rfc3339_z(fc.utc_now())


def test_normalize_name_folds_case_and_whitespace():
    assert fc.normalize_name("  Ada   LOVELACE ") == "ada lovelace"
    assert fc.normalize_name("Ada\tLovelace\n") == "ada lovelace"


def test_normalize_name_preserves_genuine_distinctness():
    """Must not merge distinct subjects by stripping punctuation or diacritics."""
    assert fc.normalize_name("Muller") != fc.normalize_name("Müller")
    assert fc.normalize_name("OBrien") != fc.normalize_name("O'Brien")
    assert fc.normalize_name("Smith Jr.") != fc.normalize_name("Smith")


def test_identifier_pattern_matches_contract():
    assert fc.is_identifier("e.1")
    assert fc.is_identifier("entity:abc-123_x")
    assert not fc.is_identifier("has space")
    assert not fc.is_identifier("")
    assert not fc.is_identifier("x" * 129)
    assert not fc.is_identifier("../escape")


def test_digest_bytes_differs_from_record_digest():
    assert fc.digest_bytes(b"hello").startswith("sha256:")
    assert fc.digest_bytes(b"hello") != fc.digest("hello")
