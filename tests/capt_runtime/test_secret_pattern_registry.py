"""Donor convergence R1 — gitleaks-derived credential pattern registry tests.

Provenance under test: gitleaks/gitleaks @
b58d3f102cf3a2c84cb7f923d05c25c9b1aed84b (MIT, (c) 2019 Zachary Rice),
adapted into ``capt_runtime/secret_patterns.py``.

Discrimination strategy (both directions):
- every registered pattern family has an assembled fixture that MUST be
  detected and redacted in every wired layer — deleting a pattern fails;
- the registry and the fixture table must stay bijective — adding a pattern
  without a fixture fails;
- benign digest/prose strings MUST survive the registry and the flight layer —
  an over-broad regex mutant fails;
- a token under a BENIGN key name must not leave a ``.capt-flight`` bundle in
  clear text — removing the flight wiring fails the export test.

All credential-shaped fixtures are assembled at runtime so no source line
contains a contiguous credential literal (repository convention).
"""

from __future__ import annotations

import json
import zipfile

from capt_runtime.discovery.redaction import redact_text as discovery_redact
from capt_runtime.flight_recorder import export_flight, redact as flight_redact, verify_flight
from capt_runtime.secret_patterns import (
    CREDENTIAL_PATTERNS,
    find_credential_shapes,
    redact_credential_shapes,
)
from capt_runtime.store import EventStore
from capt_solo.memory.secrets import screen


# --------------------------------------------------------------------------
# Runtime-assembled fixtures, keyed by registry label.
# --------------------------------------------------------------------------
def _aws_key() -> str:
    return "AK" + "IA" + "IOSFODNN7EXAMPLE"  # 16 chars after the prefix


def _fixture(label: str) -> str:
    if label == "private_key":
        return "-----BEGIN " + "RSA PRIVATE KEY-----"
    if label == "aws_access_key":
        return _aws_key()
    if label == "github_pat":
        return "ghp_" + "0123456789abcdefghijklmnopqrstuvwx"
    if label == "github_fine_grained_pat":
        return "github_pat_" + ("A1b2_" * 8)
    if label == "gitlab_pat":
        return "glpat-" + "AbCdEfGhIjKlMnOpQrSt"
    if label == "huggingface_token":
        return "hf_" + "abcdef0123456789abcdef012345678901"
    if label == "npm_token":
        return "npm_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"
    if label == "linear_api_key":
        return "lin_api_" + ("a" * 40)
    if label == "google_api_key":
        return "AIza" + ("Sy" + ("b" * 33))
    if label == "stripe_key":
        return "sk" + "_live_" + ("a" * 24)
    if label == "slack_token":
        return "xo" + "xb-" + ("1" * 10) + "-" + ("a" * 10)
    if label == "slack_webhook":
        return "https://hooks.slack.com/services/" + "T0ABCDE12/" + "B0ABCDE12/" + ("a" * 24)
    if label == "openrouter_api_key":
        return "sk-" + "or-v1-" + ("a1b2" * 8)
    if label == "openai_style_key":
        return "sk-" + ("x" * 32)
    if label == "jwt":
        return (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
            + "."
            + "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpPQiJ9"
            + "."
            + "c2lnbmF0dXJlLXNpZ25hdHVyZS0xMjM0NTY3ODkw"
        )
    raise AssertionError(f"no fixture registered for pattern label {label!r}")


def _all_fixtures() -> dict:
    return {label: _fixture(label) for label, _rule, _pat in CREDENTIAL_PATTERNS}


# --------------------------------------------------------------------------
# Registry-level discrimination
# --------------------------------------------------------------------------
def test_registry_and_fixtures_are_bijective():
    """A pattern may not be added without a fixture; a fixture may not rot."""
    labels = [label for label, _rule, _pat in CREDENTIAL_PATTERNS]
    assert len(labels) == len(set(labels)), "duplicate pattern labels in registry"
    assert set(labels) == set(_all_fixtures()), (
        "CREDENTIAL_PATTERNS and the fixture table must stay bijective"
    )


def test_every_registered_family_is_detected_and_redacted():
    for label, fixture in _all_fixtures().items():
        hits = find_credential_shapes(fixture)
        assert label in hits, f"pattern {label!r} failed to detect its own fixture"
        scrubbed = redact_credential_shapes(fixture)
        assert fixture not in scrubbed, f"pattern {label!r} did not redact its fixture"
        assert "[REDACTED_KEY]" in scrubbed


def test_find_credential_shapes_is_sorted_and_unique():
    fixture = _fixture("aws_access_key") + " " + _fixture("github_pat")
    hits = find_credential_shapes(fixture)
    assert hits == sorted(set(hits))
    assert "aws_access_key" in hits and "github_pat" in hits


def test_benign_strings_survive_registry():
    digest = "sha256:" + ("a1b2c3d4" * 8)
    benign = [
        digest,
        "The character sequence " + ("AK" + "IA" + "XYZ") + " appears in docs.",
        "uuid 4f1a2b3c-9d8e-4a5b-8c7d-0e1f2a3b4c5d",
        "release note: sk-2 is a keyboard key, not a key",
        "build succeeded in 12ms, deploying to prod",
        "ContextPackDigest: " + digest,
    ]
    for text in benign:
        assert find_credential_shapes(text) == [], f"false positive on: {text!r}"
        assert redact_credential_shapes(text) == text


# --------------------------------------------------------------------------
# Layer 1 — flight bundle (forensic export) redaction
# --------------------------------------------------------------------------
def test_flight_redact_scrubs_tokens_under_benign_keys():
    note = "provider said: " + _fixture("openrouter_api_key")
    payload = {
        "note": note,                      # benign key name, hostile value
        "lines": [_fixture("github_pat")],  # list value
        "digest": "sha256:" + ("f00dfeed" * 8),
        "api_key": _fixture("stripe_key"),  # secret key name (pre-existing path)
    }
    out = flight_redact(payload)
    dumped = json.dumps(out)
    assert _fixture("openrouter_api_key") not in dumped
    assert _fixture("github_pat") not in dumped
    assert _fixture("stripe_key") not in dumped
    assert out["api_key"] == "<redacted>"
    # Flight exports must NOT adopt discovery's generic digest clobbering:
    # ledger/manifest digests must remain verifiable in the bundle.
    assert out["digest"] == payload["digest"]


def test_flight_bundle_export_leaves_no_credential_in_clear_text(tmp_path):
    """End-to-end RED test: pre-wiring, a token under a benign key survived
    ``export_flight``; the registry wiring must make this fail closed."""
    store = EventStore(str(tmp_path / "runtime.db"))
    secret_note = "attach this key to the run: " + _fixture("github_fine_grained_pat")
    path = tmp_path / "bundle.capt-flight"
    manifest = export_flight(
        store,
        path,
        bundle_id="secret-pattern-1",
        created_at="2026-09-24T00:00:00Z",
        runtime_metadata={"modelNote": secret_note},
    )
    store.close()

    verified = verify_flight(path)
    assert verified["manifestDigest"] == manifest["manifestDigest"]

    with zipfile.ZipFile(str(path), "r") as zf:
        archive = b"".join(zf.read(name) for name in zf.namelist())
    assert _fixture("github_fine_grained_pat").encode() not in archive
    assert b"<redacted>" in archive


# --------------------------------------------------------------------------
# Layer 2 — discovery evidence redaction
# --------------------------------------------------------------------------
def test_discovery_redaction_covers_registry_families():
    for label, fixture in _all_fixtures().items():
        out = discovery_redact("evidence: " + fixture)
        assert fixture not in out, f"discovery redaction leaked {label!r}"
        assert "[REDACTED_" in out


def test_discovery_redaction_keeps_existing_behavior():
    # Pre-existing prefixed-token behavior still applies (marker contract).
    legacy = "tok " + ("sk" + "-" + ("a" * 20))
    out = discovery_redact(legacy)
    assert legacy not in out
    assert "[REDACTED_KEY]" in out
    # secret-named key assignments still redact to [REDACTED]
    assigned = "OPENAI_API_KEY=" + ("sk" + "-" + ("b" * 20))
    out2 = discovery_redact(assigned)
    assert ("sk" + "-" + ("b" * 20)) not in out2


# --------------------------------------------------------------------------
# Layer 3 — durable memory secret screening
# --------------------------------------------------------------------------
def test_memory_screen_detects_bare_provider_keys_without_keyword():
    """Regression: a bare OpenRouter-style key with no assignment keyword
    previously passed ``screen()`` and could persist into durable memory."""
    bare = "sk-" + "or-v1-" + ("c3d4" * 8)
    has, reasons, redacted = screen("run context: " + bare + " was requested")
    assert has
    assert any("provider_key" in r for r in reasons)
    assert bare not in redacted
    assert "[provider_key-REDACTED]" in redacted or "REDACTED" in redacted


def test_memory_screen_detects_sts_and_gitlab_and_jwt():
    asia = "AS" + "IA" + "IOSFODNN7EXAMPLE"
    has, reasons, redacted = screen("env: " + asia)
    assert has and asia not in redacted

    glpat = "glpat-" + "Zq7Xw9Rt2Yb4Kd6Fh8Jl"
    has, reasons, redacted = screen(glpat)
    assert has and glpat not in redacted

    head = "eyJ" + "hbGciOiJIUzI1NiJ9"
    body = "eyJ" + "zdWIiOiIxMjM0In0"
    sig = ("c2ln" * 6)[:24]
    jwt = head + "." + body + "." + sig
    has, reasons, redacted = screen("token " + jwt)
    assert has and jwt not in redacted


def test_memory_screen_benign_text_still_clean():
    for text in [
        "just some normal text about memory",
        "The character sequence " + ("AK" + "IA" + "XYZ") + " appears in docs.",
        "sha256:" + ("0f1e2d3c" * 8),
    ]:
        has, _reasons, redacted = screen(text)
        assert not has, f"false positive in memory screen: {text!r}"
        assert redacted == text


# --------------------------------------------------------------------------
# Provenance retention
# --------------------------------------------------------------------------
def test_registry_provenance_notice_is_retained():
    import capt_runtime.secret_patterns as mod

    source = open(mod.__file__, encoding="utf-8").read()
    assert "b58d3f102cf3a2c84cb7f923d05c25c9b1aed84b" in source, (
        "frozen upstream SHA must stay visible in the adapted module"
    )
    assert "MIT License" in source and "Zachary Rice" in source
    assert "gitleaks" in source
