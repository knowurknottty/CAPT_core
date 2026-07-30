"""Negative and positive checks for the machine-enforced release authority."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from capt_solo.release_validation import result_document, validate_release


REPO = Path(__file__).resolve().parents[1]


def _failures(root: Path):
    return {
        check.check_id
        for check in validate_release(root)
        if check.status == "fail"
    }


@pytest.fixture()
def release_copy(tmp_path):
    destination = tmp_path / "release-copy"
    shutil.copytree(
        REPO,
        destination,
        ignore=shutil.ignore_patterns(
            ".git",
            ".capt_state",
            ".capt_verify",
            "__pycache__",
            "build",
            "dist",
            "*.egg-info",
        ),
    )
    return destination


@pytest.fixture()
def git_clone(tmp_path):
    """A real git clone of REPO so the validator's git path executes."""
    destination = tmp_path / "release-clone"
    subprocess.run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(REPO), str(destination)],
        check=True,
        capture_output=True,
    )
    return destination


def test_live_release_semantics_pass():
    # On a SOURCE commit whose manifest names itself, final validation must
    # pass fully (clean tree, sha_match source context). This test runs against
    # REPO; it only passes once the manifest's candidate_sha equals HEAD.
    result = result_document(validate_release(REPO, final=True))
    assert result["ok"] is True, result


def test_final_validation_fails_on_dirty_tree(git_clone):
    # Integration test: a dirty working tree must make final validation FAIL,
    # and the failing check must be candidate.clean_tree specifically. We never
    # normalize a dirty candidate as passing.
    (git_clone / "capt_solo" / "dirty_marker.py").write_text("# intentional\n")
    result = result_document(validate_release(git_clone, final=True))
    assert result["ok"] is False, result
    failed_ids = [c["check_id"] for c in result["checks"] if c["status"] == "fail"]
    assert "candidate.clean_tree" in failed_ids, result


def test_candidate_sha_must_match_head(git_clone):
    # Unit test for the provenance check: a mismatched manifest SHA must fail
    # and must NOT be reported as a match. The evidence discloses the divergent
    # manifest/head values rather than asserting a matching pair.
    manifest = git_clone / "docs" / "release" / "PUBLIC_API_MANIFEST_V0.5.json"
    data = json.loads(manifest.read_text())
    data["candidate_sha"] = "0" * 40
    manifest.write_text(json.dumps(data, indent=2))
    result = result_document(validate_release(git_clone, final=True))
    sha_match = next(c for c in result["checks"] if c["check_id"] == "candidate.sha_match")
    assert sha_match["status"] == "fail", result
    assert "manifest=" in sha_match["evidence"] and "head=" in sha_match["evidence"], result


def test_version_drift_fails_closed(release_copy):
    plugin = release_copy / "capt_solo/plugin/plugin.json"
    data = json.loads(plugin.read_text(encoding="utf-8"))
    data["version"] = "9.9.9"
    plugin.write_text(json.dumps(data), encoding="utf-8")
    assert "version.identity" in _failures(release_copy)


def test_schema_drift_fails_closed(release_copy):
    stability = release_copy / "docs/PUBLIC_API_STABILITY.md"
    stability.write_text(
        stability.read_text(encoding="utf-8").replace("schema v5", "schema v4"),
        encoding="utf-8",
    )
    assert "schema.identity" in _failures(release_copy)


def test_stale_live_state_fails_closed(release_copy):
    current = release_copy / "CURRENT_STATE.md"
    current.write_text(
        current.read_text(encoding="utf-8")
        + "\nHistorical branch asserted as live: integration/full-public-architecture\n",
        encoding="utf-8",
    )
    assert "authority.live_state_freshness" in _failures(release_copy)


def test_public_inventory_drift_fails_closed(release_copy):
    manifest_path = release_copy / "docs/release/PUBLIC_API_MANIFEST_V0.5.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["packages"]["provisional"].remove("capt_solo.evidence")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert "public_api.package_inventory" in _failures(release_copy)


def test_sole_public_api_claim_fails_closed(release_copy):
    readme = release_copy / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8") + "\nThis is the sole public API.\n",
        encoding="utf-8",
    )
    assert "public_api.no_sole_facade_claim" in _failures(release_copy)
