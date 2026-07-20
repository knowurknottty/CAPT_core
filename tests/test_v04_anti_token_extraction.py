"""CAPT Solo v0.4.1 — Anti-Token-Extraction component integration tests.

These exercise the 9 required scenarios:
  1. component absent
  2. healthy installation
  3. incorrect commit/version
  4. MCP startup failure
  5. unsafe cache configuration
  6. secret-bearing schema rejection
  7. scoped degradation
  8. bootstrap idempotency
  9. legacy-cache purge behavior

The bundled stdio server (``_ate_stdio_server.py``) is the local child process
used for all spawn-based tests, so no network or external binary is required.
"""

import os
import json
import tempfile
from pathlib import Path

import pytest

from capt_solo.components.anti_token_extraction import (
    AntiTokenExtractionComponent, ATEManifest, ComponentUnavailable,
    UnsafeConfiguration, COMPONENT_ID, PINNED_COMMIT,
    load_manifest, save_manifest, purge_legacy_cache,
    register_capability,
)
from capt_solo.foundry import CapabilityRegistry, ClaimGuard, ProofEngine
from capt_solo.memory.engine import MemoryEngine


@pytest.fixture
def ate_home(tmp_path, monkeypatch):
    """Isolated home + manifest redirect so tests never touch the source tree."""
    monkeypatch.setenv("CAPT_SOLO_HOME", str(tmp_path))
    manifest = tmp_path / "ate_manifest.json"
    monkeypatch.setenv("CAPT_ATE_MANIFEST_PATH", str(manifest))
    return tmp_path


def test_1_component_absent(ate_home, monkeypatch):
    """With no manifest and no bootstrapped state, the component is 'absent'
    and reports status without raising."""
    comp = AntiTokenExtractionComponent()
    disc = comp.discover()
    assert disc["state"] == "absent"
    assert disc["server_present"] is True  # bundled server exists
    status = comp.status()
    assert status["state"] == "absent"
    # absence is not a failure: health reports not-healthy but does not raise
    assert comp.health_check()["healthy"] is False


def test_2_healthy_installation(ate_home):
    """After bootstrap, the component is present-ok, healthy, and pinned."""
    comp = AntiTokenExtractionComponent()
    res = comp.bootstrap()
    assert res["bootstrapped"] is True
    disc = comp.discover()
    assert disc["state"] == "present-ok"
    assert disc["pinned_match"] is True
    health = comp.health_check()
    assert health["healthy"] is True
    # extraction works end-to-end via the local child process
    out = comp.extract("connect with AKIA1234567890ABCDEF and move on")
    types = {t["type"] for t in out["tokens"]}
    assert "aws_access_key" in types


def test_3_incorrect_commit_version(ate_home):
    """A manifest with a wrong installed_commit is reported as mismatch and
    fails the pinned-commit verification (no silent acceptance)."""
    bad = ATEManifest(installed_commit="deadbeef" * 5)
    save_manifest(bad)
    comp = AntiTokenExtractionComponent()
    disc = comp.discover()
    assert disc["state"] == "present-mismatch"
    assert comp.verify_pinned_commit() is False
    # health check refuses to serve a mismatched install
    assert comp.health_check()["healthy"] is False


def test_4_mcp_startup_failure(ate_home, monkeypatch):
    """Pointing the component at a nonexistent executable yields a clean
    ComponentUnavailable (degrades only this capability, no crash)."""
    # Force the server path to a missing file.
    import capt_solo.components.anti_token_extraction as mod
    monkeypatch.setattr(mod, "stdio_server_path",
                         lambda: Path("/nonexistent/ate_server.py"))
    comp = AntiTokenExtractionComponent()
    # discover still works (server_present False -> absent)
    assert comp.discover()["server_present"] is False
    with pytest.raises(ComponentUnavailable):
        comp.extract("anything")


def test_5_unsafe_cache_configuration(ate_home):
    """A manifest requesting cache_mode != 'off' is rejected by validation,
    preventing an unsafe configuration from being persisted."""
    bad = ATEManifest(cache_mode="on")
    with pytest.raises(UnsafeConfiguration):
        save_manifest(bad)
    # And the live component refuses to run with cache on.
    comp = AntiTokenExtractionComponent()
    comp.manifest = ATEManifest(cache_mode="on")
    with pytest.raises(UnsafeConfiguration):
        comp.extract("token AKIA1234567890ABCDEF")


def test_6_secret_bearing_schema_rejection(ate_home):
    """Sensitive input is refused before any child process is spawned."""
    comp = AntiTokenExtractionComponent()
    comp.bootstrap()
    secret_text = "my password=supersecret123 and api_key=abcdef1234567890abcdef"
    with pytest.raises(UnsafeConfiguration):
        comp.extract(secret_text)


def test_7_scoped_degradation(ate_home):
    """When the anti-token-extraction capability degrades, ONLY that capability
    is reported degraded — other capabilities remain unaffected."""
    eng = MemoryEngine()
    try:
        pe = ProofEngine(eng._conn)
        reg = CapabilityRegistry(eng._conn, pe)
        cg = ClaimGuard(reg, pe)
        # register ATE + an unrelated capability
        register_capability(reg)
        reg.register("memory-search", "Search memory", "capt-solo",
                     lifecycle="verified")
        # degrade ONLY anti-token-extraction, scoped
        reg.degrade(COMPONENT_ID, "component_degraded",
                    affected_scope="anti-token-extraction")
        # ATE claim is downgraded
        v_ate = cg.verify_claim("Token extraction complete and verified.",
                                capability_id=COMPONENT_ID)
        assert v_ate.supported is False
        assert "not globally revoked" in v_ate.language
        # unrelated capability still verified
        v_other = cg.verify_claim("Memory search complete and verified.",
                                  capability_id="memory-search")
        assert v_other.supported is True
        # ATE degradation record is scoped, not global
        recs = reg.get_degradations(COMPONENT_ID)
        assert recs[0]["affected_scope"] == "anti-token-extraction"
        assert reg.get("memory-search").lifecycle == "verified"
    finally:
        eng.close()


def test_8_bootstrap_idempotency(ate_home):
    """Calling bootstrap twice produces no duplicate work and is idempotent."""
    comp = AntiTokenExtractionComponent()
    r1 = comp.bootstrap()
    assert r1["bootstrapped"] is True
    r2 = comp.bootstrap()
    assert r2["bootstrapped"] is False
    assert r2["idempotent"] is True
    # manifest persists the pinned commit
    assert load_manifest().installed_commit == PINNED_COMMIT


def test_9_legacy_cache_purge(ate_home, monkeypatch):
    """Bootstrap purges legacy cache directories; re-bootstrap does not error
    when they are already gone (idempotent purge)."""
    # Create a legacy cache dir under the test home.
    legacy = Path(os.environ["CAPT_SOLO_HOME"]) / "ate_cache"
    legacy.mkdir()
    (legacy / "stale.bin").write_text("x")
    assert legacy.exists()
    comp = AntiTokenExtractionComponent()
    res = comp.bootstrap()
    assert any("ate_cache" in p for p in res["legacy_cache_purged"])
    assert not legacy.exists()
    # Second bootstrap: legacy already gone, still idempotent
    res2 = comp.bootstrap()
    assert res2["idempotent"] is True
