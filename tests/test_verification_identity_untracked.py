"""FULL verification identity must include untracked files.

Regression coverage for the recovered security candidate
`verification-identity:capt_solo/verification/identity.py:54`.

Original defect: the FULL scope VSI was built only from `git ls-files`
(tracked files). An untracked module under a packaged path was invisible to the
identity, so prior verification could be reused for a tree whose effective
content differed — enabling release-evidence spoofing or package-boundary
leakage.

Fixed behaviour: `_scoped_files` for FULL also enumerates untracked,
non-ignored files via `git ls-files --others --exclude-standard`, so an added
untracked module changes the identity and blocks silent reuse.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from capt_solo.verification.identity import build_vsi
from capt_solo.verification.scope import VerificationScope


def _git(work: Path, *a: str) -> str:
    return subprocess.run(["git", "-C", str(work), *a], check=True,
                           capture_output=True, text=True).stdout


@pytest.fixture()
def repo_copy(tmp_path: Path) -> Path:
    work = tmp_path / "repo"
    work.mkdir()
    _git(work, "init", "--quiet")
    _git(work, "config", "user.email", "t@t")
    _git(work, "config", "user.name", "t")
    (work / "pyproject.toml").write_text("[project]\nname='x'\n")
    pkg = work / "capt_solo" / "memory"
    pkg.mkdir(parents=True)
    (pkg / "subject.py").write_text("VALUE = 1\n")
    _git(work, "add", "-A")
    _git(work, "commit", "--quiet", "-m", "init")
    return work


def test_untracked_module_changes_full_vsi(repo_copy: Path):
    before = build_vsi(repo_copy, VerificationScope.FULL, "python -m pytest")

    # Add an untracked module under a packaged path.
    (repo_copy / "capt_solo" / "memory" / "injected.py").write_text("VALUE = 'pwned'\n")

    after = build_vsi(repo_copy, VerificationScope.FULL, "python -m pytest")

    assert "capt_solo/memory/injected.py" in after.scope_file_hashes, (
        "untracked module must be part of the FULL VSI"
    )
    assert before.scope_file_hashes != after.scope_file_hashes, (
        "adding an untracked module must change the identity"
    )


def test_ignored_artifacts_still_excluded(repo_copy: Path):
    """gitignored content (e.g. .venv) must NOT enter the identity."""
    (repo_copy / ".gitignore").write_text(".venv/\n")
    venv = repo_copy / ".venv"
    venv.mkdir()
    (venv / "x.py").write_text("VALUE = 9\n")
    _git(repo_copy, "add", "-A")
    _git(repo_copy, "commit", "--quiet", "-m", "add venv")

    # Add an untracked .venv file after commit.
    (venv / "y.py").write_text("VALUE = 0\n")

    vsi = build_vsi(repo_copy, VerificationScope.FULL, "python -m pytest")
    assert not any(".venv" in p for p in vsi.scope_file_hashes), (
        "gitignored .venv content must remain excluded from the identity"
    )
