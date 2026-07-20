"""Security and isolation tests for Anti-Token-Extraction integration."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import capt_solo.components.anti_token_extraction as ate
from capt_solo.components.anti_token_extraction import (
    ATEManifest,
    AntiTokenExtractionComponent,
    ComponentUnavailable,
    PINNED_COMMIT,
    PINNED_VERSION,
    UnsafeConfiguration,
    load_manifest,
    purge_legacy_cache,
    save_manifest,
)


@pytest.fixture
def ate_home(tmp_path, monkeypatch):
    monkeypatch.setenv("CAPT_SOLO_HOME", str(tmp_path))
    monkeypatch.setenv("CAPT_ATE_MANIFEST_PATH", str(tmp_path / "components" / "manifest.json"))
    return tmp_path


def good_provenance():
    return {"version": PINNED_VERSION, "commit": PINNED_COMMIT, "url": ate.UPSTREAM_REPO}


def test_absent_package_is_scoped_degradation(ate_home, monkeypatch):
    monkeypatch.setattr(ate, "installed_provenance", lambda: {"version": None, "commit": None, "url": None})
    component = AntiTokenExtractionComponent()
    assert component.discover()["state"] == "absent"
    assert component.health_check()["healthy"] is False


def test_bootstrap_requires_real_pinned_provenance(ate_home, monkeypatch):
    monkeypatch.setattr(ate, "installed_provenance", lambda: {"version": PINNED_VERSION, "commit": "deadbeef", "url": ate.UPSTREAM_REPO})
    result = AntiTokenExtractionComponent().bootstrap()
    assert result["healthy"] is False
    assert load_manifest() is None


def test_bootstrap_records_verified_pin_only(ate_home, monkeypatch):
    monkeypatch.setattr(ate, "installed_provenance", good_provenance)
    result = AntiTokenExtractionComponent().bootstrap()
    assert result["healthy"] is True
    manifest = load_manifest()
    assert manifest is not None
    assert manifest.installed_commit == PINNED_COMMIT
    assert manifest.installed_version == PINNED_VERSION


def test_bootstrap_is_idempotent(ate_home, monkeypatch):
    monkeypatch.setattr(ate, "installed_provenance", good_provenance)
    first = AntiTokenExtractionComponent().bootstrap()
    second = AntiTokenExtractionComponent().bootstrap()
    assert first["bootstrapped"] is True
    assert second["idempotent"] is True


def test_unsafe_manifest_is_rejected(ate_home):
    with pytest.raises(UnsafeConfiguration):
        save_manifest(ATEManifest(cache_mode="memory"))
    with pytest.raises(UnsafeConfiguration):
        save_manifest(ATEManifest(sensitive_input_refusal=False))
    with pytest.raises(UnsafeConfiguration):
        save_manifest(ATEManifest(transport="http"))


def test_manifest_write_is_not_symlink_following(ate_home):
    target = ate_home / "target.json"
    path = Path(os.environ["CAPT_ATE_MANIFEST_PATH"])
    path.parent.mkdir(parents=True)
    path.symlink_to(target)
    with pytest.raises(UnsafeConfiguration):
        save_manifest(ATEManifest())
    assert not target.exists()


def test_legacy_cache_purge_refuses_symlink(ate_home):
    outside = ate_home / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep")
    link = ate_home / "ate_cache"
    link.symlink_to(outside, target_is_directory=True)
    removed = purge_legacy_cache()
    assert str(link) not in removed
    assert (outside / "keep.txt").read_text() == "keep"


def test_request_size_is_bounded(ate_home, monkeypatch):
    monkeypatch.setattr(ate, "installed_provenance", good_provenance)
    component = AntiTokenExtractionComponent()
    component.manifest.installed_commit = PINNED_COMMIT
    component.manifest.installed_version = PINNED_VERSION
    save_manifest(component.manifest)
    with pytest.raises(UnsafeConfiguration):
        component.compress("x" * (ate.MAX_REQUEST_BYTES + 1))


def test_no_credential_extraction_implementation_remains():
    server = ate.stdio_server_path().read_text(encoding="utf-8")
    forbidden = ["aws_access_key", "github_token", "slack_token", "stripe_key", '"match": m.group']
    for marker in forbidden:
        assert marker not in server
    assert "rtk_compress" in server
    assert "process_sensitive_input" in server


def test_mcp_template_uses_real_upstream_server():
    path = Path(ate.__file__).with_name("anti_token_extraction.mcp.json")
    config = json.loads(path.read_text())
    assert config["mcp_server"]["args"] == ["-m", "anti_token_extraction.server"]
    assert config["mcp_server"]["credentials_in_args"] is False
    assert config["mcp_server"]["network_enabled"] is False


def test_child_startup_failure_is_contained(ate_home, monkeypatch):
    monkeypatch.setattr(ate, "installed_provenance", good_provenance)
    component = AntiTokenExtractionComponent()
    component.manifest.installed_commit = PINNED_COMMIT
    component.manifest.installed_version = PINNED_VERSION
    save_manifest(component.manifest)
    monkeypatch.setattr(ate, "stdio_server_path", lambda: Path("/missing/server.py"))
    with pytest.raises(ComponentUnavailable):
        component.compress("plain build output")
