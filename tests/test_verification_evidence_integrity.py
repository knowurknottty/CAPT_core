"""Verification engine must not relabel failed evidence as current.

Regression coverage for the recovered security candidates
`verification-evidence:capt_solo/verification/engine.py:164` and
`verification-routing:capt_solo/verification/engine.py:145`.

Two defects are covered:

1. A prior record whose evidence reports failures was reused and relabelled
   VERIFICATION_CURRENT, so failed test evidence could be accepted as current
   verification.

2. A failed run was stored with status VERIFICATION_REQUIRED and confidence 1.0,
   i.e. recorded as a clean (re)verification.

Both are fixed: a prior record with failed > 0 is not reused; a fresh run that
reports failures is stored as VERIFICATION_INVALIDATED with confidence 0.0.
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


def _failing_runner(scope):
    return VerificationEvidence(
        location="pytest", summary="1 failed", passed=0, failed=1,
        command="python -m pytest",
    )


def _passing_runner(scope):
    return VerificationEvidence(
        location="pytest", summary="1 passed", passed=1, failed=0,
        command="python -m pytest",
    )


def test_failed_prior_evidence_is_not_reused_as_current(repo_copy: Path):
    store = VerificationStore(repo_copy / ".capt_verify" / "records.json")
    engine = VerificationEngine(repo=repo_copy, store=store, runner=_failing_runner)

    first = engine.verify(VerificationScope.MEMORY)
    assert first.evidence.failed == 1

    second = engine.verify(VerificationScope.MEMORY)
    assert second.status.value != "verification_current", (
        "failed evidence must not be relabelled verification_current"
    )
    assert second.evidence.failed == 1


def test_failed_run_is_stored_invalidated_not_required(repo_copy: Path):
    store = VerificationStore(repo_copy / ".capt_verify" / "records.json")
    engine = VerificationEngine(repo=repo_copy, store=store, runner=_failing_runner)

    result = engine.verify(VerificationScope.MEMORY)
    rec = store.latest_for_scope(VerificationScope.MEMORY.value)

    assert result.status.value == "verification_invalidated", (
        f"failed run must be INVALIDATED, got {result.status.value}"
    )
    assert rec["status"] == "verification_invalidated"
    assert rec["confidence"] == 0.0, "failed run must not claim confidence 1.0"


def test_passing_run_is_stored_current_and_reusable(repo_copy: Path):
    store = VerificationStore(repo_copy / ".capt_verify" / "records.json")
    engine = VerificationEngine(repo=repo_copy, store=store, runner=_passing_runner)

    first = engine.verify(VerificationScope.MEMORY)
    assert first.evidence.failed == 0

    second = engine.verify(VerificationScope.MEMORY)
    assert second.status.value == "verification_current", (
        "clean prior evidence should be reusable as current"
    )
