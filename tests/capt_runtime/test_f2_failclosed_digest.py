"""Adversarial F2 regression: an unreadable path must not certify an unchanged tree."""

from pathlib import Path

import pytest

from capt_runtime.verification import (
    VerificationFailure,
    _tree_digest,
    verify_repository_unchanged,
)


def test_unreadable_file_fails_closed_instead_of_being_skipped(tmp_path, monkeypatch):
    readable = tmp_path / "readable.py"
    unreadable = tmp_path / "unreadable.py"
    readable.write_text("before", encoding="utf-8")
    unreadable.write_text("old-secret", encoding="utf-8")
    actual_read_bytes = Path.read_bytes

    def simulate_unreadable(path):
        if path == unreadable:
            raise OSError("synthetic failure reading protected file")
        return actual_read_bytes(path)

    # The source implementation used to skip unreadable files and return a
    # digest anyway, letting a mutation of the excluded path go unnoticed.
    monkeypatch.setattr(Path, "read_bytes", simulate_unreadable)
    with pytest.raises(VerificationFailure, match="unreadable.py"):
        _tree_digest(str(tmp_path))


def test_tree_digest_detects_mutation_to_readable_file(tmp_path):
    target = tmp_path / "app.py"
    target.write_text("x = 1\n", encoding="utf-8")
    baseline = _tree_digest(str(tmp_path))
    assert verify_repository_unchanged(str(tmp_path), baseline)
    target.write_text("x = 2\n", encoding="utf-8")
    assert not verify_repository_unchanged(str(tmp_path), baseline)
