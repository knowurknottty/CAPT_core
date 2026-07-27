"""Tests for the Verified State Identity (VSI) verification subsystem.

Demonstrates the acceptance criteria:
- unchanged state reuses verification correctly;
- changed HEAD invalidates prior verification;
- dirty working tree invalidates only affected scopes;
- documentation-only changes avoid unnecessary full-suite runs;
- targeted verification selection;
- evidence reuse;
- no verification loops.
"""
import os
import sys
import tempfile
import json

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from capt_solo.verification import (
    VerificationEngine, VerificationStore, VerificationScope,
    build_vsi, vsi_equivalent, diff_vsi, VerifiedStateIdentity,
    VerificationStatus, map_paths_to_scopes, select_scope_for_changes,
)


class _FakeRunner:
    """Records calls; does not run pytest. Returns a dummy evidence location."""
    def __init__(self):
        self.calls = []
    def __call__(self, scope):
        self.calls.append(scope)
        loc = os.path.join(tempfile.gettempdir(), f"fake-ev-{scope.value}.txt")
        from capt_solo.verification import VerificationEvidence
        return VerificationEvidence(location=loc, summary=f"ran {scope.value}",
                                    passed=1, failed=0, command=f"fake {scope.value}")


def _store(tmp):
    return VerificationStore(os.path.join(tmp, "records.jsonl"))


def test_unchanged_state_reuses_verification():
    tmp = tempfile.mkdtemp()
    store = _store(tmp)
    runner = _FakeRunner()
    eng = VerificationEngine(REPO, store=store, runner=runner)
    r1 = eng.verify(VerificationScope.ENGINE_MATH)
    assert r1.status == VerificationStatus.VERIFICATION_REQUIRED
    assert r1.ran_scope == VerificationScope.ENGINE_MATH
    assert len(runner.calls) == 1
    # Second call: identical VSI -> reuse, NO rerun.
    r2 = eng.verify(VerificationScope.ENGINE_MATH)
    assert r2.status == VerificationStatus.VERIFICATION_CURRENT
    assert r2.reused_record_id == r1.new_record_id
    assert r2.ran_scope is None
    assert len(runner.calls) == 1  # no additional run
    assert "does NOT increase confidence" in r2.confidence_note


def test_changed_head_invalidates():
    tmp = tempfile.mkdtemp()
    store = _store(tmp)
    runner = _FakeRunner()
    eng = VerificationEngine(REPO, store=store, runner=runner)
    # Store a prior record whose HEAD differs from the current repo HEAD.
    fake_vsi = build_vsi(REPO, VerificationScope.ENGINE_MATH, "fake cmd")
    fake_vsi.head_commit = "deadbeef" * 5
    from capt_solo.verification import VerificationRecord, VerificationEvidence
    rec = VerificationRecord(record_id="old", vsi=fake_vsi,
                             status=VerificationStatus.VERIFICATION_REQUIRED.value,
                             evidence=VerificationEvidence(location="/tmp/x"))
    store.add(rec)
    # Now verify: HEAD differs from the stored record -> invalidated, rerun, full.
    r2 = eng.verify(VerificationScope.ENGINE_MATH)
    assert r2.status == VerificationStatus.VERIFICATION_REQUIRED
    assert any(d["reason"] == "head_changed" for d in r2.diff_reasons)
    assert r2.ran_scope == VerificationScope.FULL  # head change -> full


def test_dirty_tree_invalidates_only_affected_scope():
    tmp = tempfile.mkdtemp()
    store = _store(tmp)
    runner = _FakeRunner()
    eng = VerificationEngine(REPO, store=store, runner=runner)
    # Baseline: verify engine_math and docs.
    eng.verify(VerificationScope.ENGINE_MATH)
    eng.verify(VerificationScope.DOCS)
    runner.calls.clear()
    # Simulate a docs-only change by writing a temp doc file and re-verifying.
    # We emulate by checking that a docs change does NOT invalidate engine_math.
    # Build a prior engine_math record, then verify engine_math again with an
    # unchanged engine file but changed doc file in the tree.
    doc_path = os.path.join(REPO, "docs", "TEMP_VSI_TEST.md")
    open(doc_path, "w").write("temp")
    try:
        # engine_math VSI should still be equivalent (doc not in its scope).
        r_math = eng.verify(VerificationScope.ENGINE_MATH)
        assert r_math.status == VerificationStatus.VERIFICATION_CURRENT
        # docs VSI changed (file added) -> re-verified (REQUIRED), and the
        # affected scope is DOCS only, not the full suite.
        r_docs = eng.verify(VerificationScope.DOCS)
        assert r_docs.status == VerificationStatus.VERIFICATION_REQUIRED
        assert r_docs.ran_scope == VerificationScope.DOCS
    finally:
        os.remove(doc_path)


def test_documentation_only_avoids_full_suite():
    tmp = tempfile.mkdtemp()
    store = _store(tmp)
    runner = _FakeRunner()
    eng = VerificationEngine(REPO, store=store, runner=runner)
    # A docs-only change should map to DOCS scope, which runs no pytest suite.
    scope = select_scope_for_changes(["README.md", "docs/foo.md"])
    assert scope == VerificationScope.DOCS
    r = eng.verify(VerificationScope.DOCS)
    # DOCS scope: runner is invoked but the production runner is a no-op for docs
    # (no pytest invocation). We assert the engine selected DOCS, not SUITE/FULL,
    # proving the full suite was avoided.
    assert r.ran_scope == VerificationScope.DOCS
    assert r.status == VerificationStatus.VERIFICATION_REQUIRED


def test_targeted_verification_selection():
    # engine file change -> narrow scope
    assert select_scope_for_changes(["capt_solo/engines/mathematics.py"]) == VerificationScope.ENGINE_MATH
    assert select_scope_for_changes(["capt_solo/engines/physics.py"]) == VerificationScope.ENGINE_PHYSICS
    # multiple engine changes -> suite
    s = select_scope_for_changes(["capt_solo/engines/mathematics.py",
                                  "capt_solo/engines/physics.py"])
    assert s == VerificationScope.SUITE
    # unknown path -> full
    assert select_scope_for_changes(["some/random/file.xyz"]) == VerificationScope.FULL


def test_evidence_reuse():
    tmp = tempfile.mkdtemp()
    store = _store(tmp)
    runner = _FakeRunner()
    eng = VerificationEngine(REPO, store=store, runner=runner)
    r1 = eng.verify(VerificationScope.MEMORY)
    r2 = eng.verify(VerificationScope.MEMORY)
    assert r2.reused_evidence is not None
    assert r2.reused_evidence.location == r1.evidence.location
    assert r2.reused_record_id == r1.new_record_id


def test_no_verification_loop():
    tmp = tempfile.mkdtemp()
    store = _store(tmp)
    runner = _FakeRunner()
    eng = VerificationEngine(REPO, store=store, runner=runner)
    # First verify runs (REQUIRED); subsequent identical verifies reuse (CURRENT).
    first = eng.verify(VerificationScope.BOUNDARY)
    assert first.status == VerificationStatus.VERIFICATION_REQUIRED
    for _ in range(4):
        res = eng.verify(VerificationScope.BOUNDARY)
        assert res.status == VerificationStatus.VERIFICATION_CURRENT
    assert len(runner.calls) == 1  # only the first actually ran


def test_vsi_equivalence_and_diff():
    a = build_vsi(REPO, VerificationScope.ENGINE_MATH, "cmd")
    b = build_vsi(REPO, VerificationScope.ENGINE_MATH, "cmd")
    assert vsi_equivalent(a, b)
    b.head_commit = "changed"
    diffs = diff_vsi(a, b)
    assert any(d["reason"] == "head_changed" for d in diffs)
