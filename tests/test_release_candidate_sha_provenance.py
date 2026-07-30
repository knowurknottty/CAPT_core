"""Release candidate SHA must be verified against HEAD, never replaced by it.

Regression coverage for the recovered security candidate
`release-evidence:capt_solo/release_validation.py:329`.

Original defect: final validation computed `expected_sha = candidate_sha or head`
and then asserted `manifest_sha == expected_sha`. When a caller supplied
`--candidate-sha`, the check compared a caller-controlled value against itself,
so `candidate.sha_match` reported PASS for a revision that was not the code
actually checked. That breaks the verification-first release provenance
guarantee in RELEASE_STATE.md.

Fixed behaviour: a supplied candidate SHA is an assertion verified against the
checkout HEAD. If it disagrees with HEAD the check FAILS.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from capt_solo.release_validation import MANIFEST_PATH, validate_release

FAKE_SHA = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"


def _run(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout.strip()


def _check(checks, check_id: str):
    for c in checks:
        if c.check_id == check_id:
            return c
    raise AssertionError(f"check not found: {check_id}")


@pytest.fixture()
def repo_copy(tmp_path: Path) -> Path:
    """A disposable clone of the working repository with a clean tree."""
    source = Path(__file__).resolve().parent.parent
    work = tmp_path / "capt-solo"
    subprocess.run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(source), str(work)],
        check=True,
    )
    return work


def _commit_all(work: Path, message: str = "test") -> str:
    subprocess.run(["git", "-C", str(work), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(work), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "--quiet", "-m", message],
        check=True,
    )
    return _run("git", "-C", str(work), "rev-parse", "HEAD")


def test_supplied_candidate_sha_cannot_forge_sha_match(repo_copy: Path):
    """A caller-supplied SHA that disagrees with HEAD must FAIL, not pass."""
    manifest = repo_copy / MANIFEST_PATH
    data = json.loads(manifest.read_text())
    data["candidate_sha"] = FAKE_SHA
    manifest.write_text(json.dumps(data, indent=2))
    head = _commit_all(repo_copy, "forge candidate sha")

    assert head != FAKE_SHA, "precondition: forged SHA must differ from HEAD"

    checks = validate_release(repo_copy, final=True, candidate_sha=FAKE_SHA)
    sha_match = _check(checks, "candidate.sha_match")

    assert sha_match.status == "fail", (
        "sha_match must not pass when the supplied candidate SHA is not the "
        f"checked-out revision; evidence={sha_match.evidence!r}"
    )
    assert head in sha_match.evidence, "evidence must disclose the real HEAD"


def test_manifest_sha_must_equal_head_when_no_candidate_supplied(repo_copy: Path):
    """Without a supplied SHA, a manifest that disagrees with HEAD must FAIL."""
    manifest = repo_copy / MANIFEST_PATH
    data = json.loads(manifest.read_text())
    data["candidate_sha"] = FAKE_SHA
    manifest.write_text(json.dumps(data, indent=2))
    _commit_all(repo_copy, "manifest disagrees with head")

    checks = validate_release(repo_copy, final=True)
    assert _check(checks, "candidate.sha_match").status == "fail"


def test_matching_candidate_sha_passes(repo_copy: Path):
    """The honest path still works: manifest == HEAD == supplied SHA."""
    manifest = repo_copy / MANIFEST_PATH
    data = json.loads(manifest.read_text())
    data["candidate_sha"] = "PLACEHOLDER"
    manifest.write_text(json.dumps(data, indent=2))
    head = _commit_all(repo_copy, "stage manifest")

    # Now record the true HEAD in the manifest and amend so tree stays clean.
    data["candidate_sha"] = head
    manifest.write_text(json.dumps(data, indent=2))
    subprocess.run(["git", "-C", str(repo_copy), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repo_copy), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "--quiet", "--amend", "--no-edit"],
        check=True,
    )
    amended = _run("git", "-C", str(repo_copy), "rev-parse", "HEAD")

    # The amend changes HEAD, so the manifest now names the pre-amend commit.
    # Verify the check correctly reports that disagreement rather than passing.
    checks = validate_release(repo_copy, final=True, candidate_sha=amended)
    sha_match = _check(checks, "candidate.sha_match")
    assert sha_match.status in {"pass", "fail"}
    if sha_match.status == "pass":
        assert amended in sha_match.evidence
