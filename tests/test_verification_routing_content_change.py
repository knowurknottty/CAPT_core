"""Verification routing must detect same-path content edits.

Regression coverage for the recovered security candidate
`verification-routing:capt_solo/verification/engine.py:145`.

Original defect: changed scoped files were computed as the symmetric difference
of the two VSI path *sets*. An in-place edit changes file content but not the
set of paths, so the difference was empty and a real code change was routed to
docs-only verification — recorded as newly verified without running the
applicable test scope.

Fixed behaviour: changed files are detected by comparing per-path content
hashes, so a same-path edit is attributed to its real scope.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from capt_solo.verification.engine import VerificationEngine
from capt_solo.verification.record import VerificationEvidence
from capt_solo.verification.scope import VerificationScope
from capt_solo.verification.store import VerificationStore


def _git(work: Path, *a: str) -> None:
    subprocess.run(["git", "-C", str(work), *a], check=True,
                   capture_output=True, text=True)


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


def _runner(scope):
    return VerificationEvidence(location="pytest", summary="ok", passed=1,
                                failed=0, command="pytest")


def test_in_place_edit_routes_to_real_scope_not_docs(repo_copy: Path):
    store = VerificationStore(repo_copy / ".capt_verify" / "records.json")
    engine = VerificationEngine(repo=repo_copy, store=store, runner=_runner)

    engine.verify(VerificationScope.FULL)

    # Edit subject.py in place WITHOUT committing: HEAD identical, tree dirty.
    (repo_copy / "capt_solo" / "memory" / "subject.py").write_text("VALUE = 2\n")

    scopes = []

    def tracking_runner(scope):
        scopes.append(scope.value if hasattr(scope, "value") else str(scope))
        return _runner(scope)

    engine2 = VerificationEngine(repo=repo_copy, store=store, runner=tracking_runner)
    engine2.verify(VerificationScope.FULL)

    assert "docs" not in scopes, (
        f"in-place code edit was routed to docs-only verification; scopes={scopes}"
    )
    # The edit must trigger a real code scope, not docs-only. The engine may
    # escalate to SUITE (broader than the specific scope) when the change is
    # outside the requested scope, which is the correct, safe behaviour.
    assert ("memory" in scopes or "suite" in scopes), (
        f"edit in capt_solo/memory must trigger a code scope; scopes={scopes}"
    )


def test_no_false_zero_change_on_content_edit(repo_copy: Path):
    store = VerificationStore(repo_copy / ".capt_verify" / "records.json")
    engine = VerificationEngine(repo=repo_copy, store=store, runner=_runner)
    engine.verify(VerificationScope.FULL)

    (repo_copy / "capt_solo" / "memory" / "subject.py").write_text("VALUE = 2\n")
    result = engine.verify(VerificationScope.FULL)

    reasons = getattr(result, "diff_reasons", []) or []
    content_change = any(
        r.get("reason") == "working_tree_changed" and "0 scoped file" in r.get("detail", "")
        for r in reasons
    )
    assert not content_change, (
        "a real content edit must not be reported as zero scoped files changed"
    )
