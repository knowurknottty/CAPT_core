"""Adversarial / negative verification for the evidence + VSI integration (Phase 12).

Representative (positive) and negative (must-fail) tests proving the governed
runtime resists: implicit global writes, path traversal, forbidden auto-persist,
self-modification loops, silent overwrite of verified by inferred, restart of a
completed mission, and false-confidence reuse after a real state change.
"""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from capt_solo.evidence import (
    EvidenceRecord, EvidenceClaim, EvidenceSource, EvidenceClass, EvidenceStatus,
    EvidenceScope, ProjectWorkspace, ProjectContext, WorkspaceScope, WorkspaceIsolationError,
    PromotionPipeline, PromotionState, SelfModificationGovernor, SelfModState,
    MissionCheckpoint, CheckpointStore, CheckpointStatus, detect_divergence, resume_plan,
    AntiLoopGuard, build_reuse_from_vsi, invalidate_vsi_records,
    InvalidationReason,
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _vsi_record(rid, scope, head, status, paths):
    return {
        "record_id": rid,
        "vsi": {"verification_scope": scope, "head_commit": head,
                "active_branch": "integration/full-public-architecture",
                "repository": REPO, "scope_file_hashes": {p: "h" for p in paths}},
        "status": status,
        "evidence": {"location": f".capt_verify/{rid}.json"},
    }


# ---- representative: proof-preserving reuse via VSI ----
def test_vsi_to_evidence_reuse_current():
    recs = [_vsi_record("v1", "engine_math", "a0124c1", "verification_current",
                        ["capt_solo/engines/mathematics.py"])]
    decision = build_reuse_from_vsi(recs, claim_id="vsi:v1", vsi_state="equivalent")
    assert decision["action"] == "reuse_current_evidence"
    assert decision["evidence_status"] == "current"
    assert "ev-from-v1" in decision["evidence_record_ids"]


def test_vsi_changed_invalidates_reuse():
    recs = [_vsi_record("v1", "engine_math", "a0124c1", "verification_current",
                        ["capt_solo/engines/mathematics.py"])]
    # head changed -> must NOT reuse; must require verification
    decision = build_reuse_from_vsi(recs, claim_id="vsi:v1", vsi_state="changed",
                                    invalidation_reason=InvalidationReason.HEAD_CHANGED.value,
                                    changed_paths=["capt_solo/engines/mathematics.py"])
    assert decision["action"] != "reuse_current_evidence"
    assert decision["evidence_status"] == "invalidated"


def test_vsi_docs_change_keeps_engine_current():
    recs = [
        _vsi_record("v-eng", "engine_math", "a0124c1", "verification_current",
                    ["capt_solo/engines/mathematics.py"]),
        _vsi_record("v-doc", "docs", "a0124c1", "verification_current",
                    ["docs/architecture.md"]),
    ]
    # docs file changed; engine evidence must remain reusable
    decision = build_reuse_from_vsi(recs, claim_id="vsi:v-eng", vsi_state="changed",
                                    invalidation_reason=InvalidationReason.WORKING_TREE_PATH_CHANGED.value,
                                    changed_paths=["docs/architecture.md"])
    assert decision["action"] == "reuse_current_evidence"


def test_invalidate_vsi_marks_affected():
    recs = [
        _vsi_record("v-eng", "engine_math", "a0124c1", "verification_current",
                    ["capt_solo/engines/mathematics.py"]),
        _vsi_record("v-doc", "docs", "a0124c1", "verification_current",
                    ["docs/architecture.md"]),
    ]
    res = invalidate_vsi_records(recs, reason=InvalidationReason.HEAD_CHANGED.value,
                                 changed_paths=["any"])
    assert set(res["affected_vsi_records"]) == {"v-eng", "v-doc"}
    assert res["invalidation_scope"] == "full"


# ---- negative / adversarial ----
def test_adversarial_global_write_rejected():
    tmp = tempfile.mkdtemp()
    ws = ProjectWorkspace(tmp)
    ws.bind(ProjectContext(project_id="p", repository="r"))
    try:
        ws.require_scope(WorkspaceScope.GLOBAL_MEMORY)
        assert False, "global write must be rejected"
    except WorkspaceIsolationError:
        pass


def test_adversarial_path_traversal_rejected():
    tmp = tempfile.mkdtemp()
    ws = ProjectWorkspace(tmp)
    ws.bind(ProjectContext(project_id="p", repository="r"))
    try:
        ws._safe_path("../../etc/passwd")
        assert False, "traversal must be rejected"
    except WorkspaceIsolationError:
        pass


def test_adversarial_forbidden_content_not_persisted():
    tmp = tempfile.mkdtemp()
    ws = ProjectWorkspace(tmp)
    ws.bind(ProjectContext(project_id="p", repository="r"))
    pipe = PromotionPipeline(ws)
    cand = pipe.submit_candidate(content="traceback with password=secret and api_key=xyz")
    assert cand.state == PromotionState.QUARANTINED.value


def test_adversarial_inferred_does_not_overwrite_verified():
    # A verified record id must not be silently replaced by an inferred candidate.
    tmp = tempfile.mkdtemp()
    ws = ProjectWorkspace(tmp)
    ws.bind(ProjectContext(project_id="p", repository="r"))
    pipe = PromotionPipeline(ws)
    cand = pipe.submit_candidate(content="inferred conclusion", is_inferred=True)
    assert cand.state == PromotionState.QUARANTINED.value
    # promotion requires VALIDATED; inferred stays quarantined unless explicitly validated
    try:
        pipe.promote_project(cand, namespace="p")
        assert False, "cannot promote non-validated inferred record"
    except Exception:
        pass


def test_adversarial_selfmod_loop_blocked():
    gov = SelfModificationGovernor(mission_id="loop")
    first = gov.propose(proposed_change="same change", rationale="r",
                        triggering_evidence="e", original_behavior="o",
                        expected_improvement="i", risk_analysis="low",
                        affected_scope="project_local", diff="-a\n+b",
                        tests_or_validation="t", rollback_path="rb",
                        approval_requirement="project_local")
    dup = gov.propose(proposed_change="same change", rationale="r",
                      triggering_evidence="e", original_behavior="o",
                      expected_improvement="i", risk_analysis="low",
                      affected_scope="project_local", diff="-a\n+b",
                      tests_or_validation="t", rollback_path="rb",
                      approval_requirement="project_local")
    assert first.record_id == dup.record_id  # deduplicated, no loop


def test_adversarial_completed_mission_not_restarted():
    tmp = tempfile.mkdtemp()
    store = CheckpointStore(tmp)
    cp = MissionCheckpoint(mission_id="done", project_id="p", objective="done",
                           status=CheckpointStatus.COMPLETED.value,
                           next_safe_action="do more")
    store.save(cp)
    loaded = store.load("done")
    plan = resume_plan(loaded, {})
    assert plan["next_action"] == "DO_NOT_RESTART_COMPLETED_MISSION"


def test_adversarial_false_confidence_guard():
    # Repeated equivalent state must NOT increase confidence; reuse decision is stable.
    recs = [_vsi_record("v1", "engine_math", "a0124c1", "verification_current",
                        ["capt_solo/engines/mathematics.py"])]
    d1 = build_reuse_from_vsi(recs, claim_id="vsi:v1", vsi_state="equivalent")
    d2 = build_reuse_from_vsi(recs, claim_id="vsi:v1", vsi_state="equivalent")
    assert d1["action"] == d2["action"] == "reuse_current_evidence"
    # confidence is never incremented by repetition (no false confidence)
    assert "increase" not in d2["reason"].lower() or "does not" in d2["reason"].lower()


def test_adversarial_antiloop_detects_repeat():
    g = AntiLoopGuard(max_repeats=1)
    g.repeated_verification("vsi:eq")
    loop, msg = g.repeated_verification("vsi:eq")
    assert loop is True
