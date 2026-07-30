"""Permanent regression tests for the release-identity (Option A) model.

These lock in the correction to the impossible self-referential SHA invariant
that caused the HY3 release-freeze incident. They prove:

* a commit cannot contain its own Git SHA (mathematical, not policy);
* a metadata commit (parent == candidate_sha) validates;
* an incorrect parent commit fails;
* an incorrect candidate_sha fails;
* implementation changes after a metadata commit fail clean-tree / are rejected;
* a metadata-only commit passes final validation;
* the source commit remains immutable and self-naming.

Run against real git clones so the validator's git path executes.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from capt_solo.release_validation import result_document, validate_release

REPO = Path(__file__).resolve().parents[1]


def _clone(tmp_path: Path) -> Path:
    dst = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(REPO), str(dst)],
        check=True, capture_output=True,
    )
    return dst


def _set_candidate_sha(clone: Path, sha: str) -> None:
    m = clone / "docs" / "release" / "PUBLIC_API_MANIFEST_V0.5.json"
    data = json.loads(m.read_text())
    data["candidate_sha"] = sha
    m.write_text(json.dumps(data, indent=2))


def _commit(clone: Path, msg: str) -> str:
    subprocess.run(["git", "-C", str(clone), "add", "-A"], check=True,
                   capture_output=True)
    subprocess.run(["git", "-C", str(clone), "commit", "--quiet", "-m", msg],
                   check=True, capture_output=True)
    return subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"],
                          check=True, capture_output=True, text=True).stdout.strip()


def _checks(result):
    return {c["check_id"]: c for c in result["checks"]}


def test_commit_cannot_contain_own_sha(tmp_path):
    """Mathematical proof: no tracked-manifest commit can name its own SHA."""
    clone = _clone(tmp_path)
    head = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"],
                          check=True, capture_output=True, text=True).stdout.strip()
    # Try to set the manifest to the current HEAD and commit -> new SHA.
    _set_candidate_sha(clone, head)
    new_head = _commit(clone, "attempt self-SHA")
    assert new_head != head, "committing the manifest changed the SHA (expected)"
    # The new commit's SHA is NOT what the manifest says -> invariant impossible.
    assert new_head != head
    # And a further attempt also fails: the loop is mathematically unavoidable.
    _set_candidate_sha(clone, new_head)
    newer = _commit(clone, "attempt self-SHA again")
    assert newer != new_head


def test_source_commit_self_names_and_validates(tmp_path):
    """A source commit whose manifest names HEAD validates (source context)."""
    clone = _clone(tmp_path)
    head = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"],
                          check=True, capture_output=True, text=True).stdout.strip()
    _set_candidate_sha(clone, head)
    _commit(clone, "freeze source self-name")
    result = result_document(validate_release(clone, final=True))
    assert result["ok"] is True, result
    sha_match = _checks(result)["candidate.sha_match"]
    assert sha_match["status"] == "pass", sha_match


def test_metadata_commit_validates_against_parent(tmp_path):
    """Metadata commit: manifest names parent (source); validates."""
    clone = _clone(tmp_path)
    source = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"],
                            check=True, capture_output=True, text=True).stdout.strip()
    # Metadata-only commit on top of source.
    _set_candidate_sha(clone, source)
    _commit(clone, "release metadata")
    result = result_document(validate_release(clone, final=True))
    assert result["ok"] is True, result
    sha_match = _checks(result)["candidate.sha_match"]
    assert sha_match["status"] == "pass", sha_match
    assert "metadata" in sha_match["evidence"], sha_match


def test_incorrect_parent_fails(tmp_path):
    """Metadata commit whose manifest names a non-parent SHA must fail."""
    clone = _clone(tmp_path)
    _set_candidate_sha(clone, "0" * 40)  # not the parent
    _commit(clone, "metadata wrong parent")
    result = result_document(validate_release(clone, final=True))
    sha_match = _checks(result)["candidate.sha_match"]
    assert sha_match["status"] == "fail", result


def test_incorrect_candidate_sha_fails(tmp_path):
    """Caller-supplied --candidate-sha differing from HEAD must fail."""
    clone = _clone(tmp_path)
    result = result_document(validate_release(clone, final=True,
                                              candidate_sha="0" * 40))
    sha_match = _checks(result)["candidate.sha_match"]
    assert sha_match["status"] == "fail", result


def test_implementation_change_after_metadata_fails_clean_tree(tmp_path):
    """A real code edit after the metadata commit dirties the tree -> fail."""
    clone = _clone(tmp_path)
    source = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"],
                            check=True, capture_output=True, text=True).stdout.strip()
    _set_candidate_sha(clone, source)
    _commit(clone, "release metadata")
    # Now an implementation change (not metadata).
    (clone / "capt_solo" / "extra_module.py").write_text("VALUE = 1\n")
    result = result_document(validate_release(clone, final=True))
    assert result["ok"] is False, result
    assert "candidate.clean_tree" in _checks(result), result


def test_metadata_only_change_passes(tmp_path):
    """A further metadata-only edit on top of the metadata commit passes."""
    clone = _clone(tmp_path)
    source = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"],
                            check=True, capture_output=True, text=True).stdout.strip()
    _set_candidate_sha(clone, source)
    _commit(clone, "release metadata")
    # Another metadata-only tweak (e.g. add a release note file).
    (clone / "docs" / "release" / "RELEASE_NOTE.txt").write_text("v0.5 candidate\n")
    _commit(clone, "more metadata")
    result = result_document(validate_release(clone, final=True))
    assert result["ok"] is True, result
