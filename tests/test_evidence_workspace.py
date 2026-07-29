"""Tests for workspace isolation, promotion, self-modification, checkpoint, metrics (Phases 5-9)."""
import os, sys, tempfile
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from capt_solo.evidence import (
    ProjectWorkspace, ProjectContext, WorkspaceScope, BindState, WorkspaceIsolationError,
    PromotionPipeline, MemoryCandidate, PromotionState, PromotionError,
    SelfModificationGovernor, SelfModState, SelfModError,
    MissionCheckpoint, CheckpointStore, CheckpointStatus, detect_divergence, resume_plan,
    AntiLoopGuard,
)


def _bound_ws(tmp):
    ws = ProjectWorkspace(tmp)
    ws.bind(ProjectContext(project_id="p1", repository="capt-solo",
                           project_memory_namespace="p1"))
    return ws


def test_valid_project_binding():
    tmp = tempfile.mkdtemp()
    ws = _bound_ws(tmp)
    assert ws.is_bound()
    assert ws.bind_state == "bound"
    assert os.path.exists(os.path.join(tmp, ".capt", "PROJECT_CONTEXT.json"))


def test_unbound_workspace_no_persistence():
    tmp = tempfile.mkdtemp()
    ws = ProjectWorkspace(tmp)  # no context file
    assert not ws.is_bound()
    assert ws.bind_state == "unbound"
    # project write rejected when unbound
    assert ws.can_write(".capt/evidence/x.json", WorkspaceScope.PROJECT_MEMORY) is False
    try:
        ws.require_scope(WorkspaceScope.PROJECT_MEMORY)
        assert False, "should raise"
    except WorkspaceIsolationError:
        pass


def test_forbidden_write_root():
    tmp = tempfile.mkdtemp()
    ws = _bound_ws(tmp)
    # forbid a root
    ws.context.forbidden_write_roots = [".capt/quarantine"]
    assert ws.can_write(".capt/quarantine/evil.json", WorkspaceScope.PROJECT_MEMORY) is False


def test_traversal_rejection():
    tmp = tempfile.mkdtemp()
    ws = _bound_ws(tmp)
    try:
        ws._safe_path("../escape.json")
        assert False, "should reject traversal"
    except WorkspaceIsolationError:
        pass


def test_symlink_escape_rejection():
    tmp = tempfile.mkdtemp()
    ws = _bound_ws(tmp)
    # create a symlink pointing outside
    outside = tempfile.mkdtemp()
    link = os.path.join(tmp, ".capt", "escape_link")
    os.symlink(outside, link)
    try:
        ws._safe_path(".capt/escape_link/secret.txt")
        # On some platforms realpath resolves the symlink; ensure it's rejected
        assert False, "symlink escape should be rejected"
    except WorkspaceIsolationError:
        pass


def test_global_write_never_implicit():
    tmp = tempfile.mkdtemp()
    ws = _bound_ws(tmp)
    try:
        ws.require_scope(WorkspaceScope.GLOBAL_MEMORY)
        assert False, "global write must be rejected"
    except WorkspaceIsolationError:
        pass


def test_promotion_workspace_candidate_local():
    tmp = tempfile.mkdtemp()
    ws = _bound_ws(tmp)
    pipe = PromotionPipeline(ws)
    cand = pipe.submit_candidate(content="accepted architectural decision",
                                 provenance=["vsi:eq"], project_namespace="p1")
    assert cand.state == PromotionState.CANDIDATE.value
    cand = pipe.validate(cand, approved=True, notes="reviewed")
    assert cand.state == PromotionState.VALIDATED.value
    pid = pipe.promote_project(cand, namespace="p1")
    assert cand.state == PromotionState.PROMOTED_PROJECT.value


def test_promotion_global_denied_without_approval():
    tmp = tempfile.mkdtemp()
    ws = _bound_ws(tmp)
    pipe = PromotionPipeline(ws)
    cand = pipe.submit_candidate(content="stable cross-project convention",
                                 provenance=["user:decision"])
    cand = pipe.validate(cand, approved=True)
    try:
        pipe.promote_global(cand, approved_by="")  # no approver
        assert False, "global promotion without approval must fail"
    except PromotionError:
        pass


def test_inferred_quarantined():
    tmp = tempfile.mkdtemp()
    ws = _bound_ws(tmp)
    pipe = PromotionPipeline(ws)
    cand = pipe.submit_candidate(content="inferred hypothesis from simulation",
                                 is_inferred=True)
    assert cand.state == PromotionState.QUARANTINED.value


def test_forbidden_content_quarantined():
    tmp = tempfile.mkdtemp()
    ws = _bound_ws(tmp)
    pipe = PromotionPipeline(ws)
    cand = pipe.submit_candidate(content="here is a stack trace with a secret token")
    assert cand.state == PromotionState.QUARANTINED.value


def test_selfmod_proposed_diffable():
    gov = SelfModificationGovernor(mission_id="m1")
    rec = gov.propose(proposed_change="update skill X",
                      rationale="improve clarity",
                      triggering_evidence="ev1",
                      original_behavior="old text",
                      expected_improvement="better",
                      risk_analysis="low",
                      affected_scope="project_local",
                      diff="-old\n+new",
                      tests_or_validation="unit test",
                      rollback_path="git revert",
                      approval_requirement="project_local")
    assert rec.status == SelfModState.PROPOSED.value
    rec = gov.approve(rec.record_id)
    assert rec.status == SelfModState.APPROVED.value
    rec = gov.apply(rec.record_id)
    assert rec.status == SelfModState.APPLIED.value


def test_selfmod_global_quarantined_and_requires_approval():
    gov = SelfModificationGovernor(mission_id="m2")
    rec = gov.propose(proposed_change="change global policy",
                      rationale="r", triggering_evidence="e",
                      original_behavior="o", expected_improvement="i",
                      risk_analysis="high", affected_scope="global_policy",
                      diff="-x\n+y", tests_or_validation="t",
                      rollback_path="rollback", approval_requirement="global_approval")
    assert rec.status == SelfModState.QUARANTINED.value
    try:
        gov.approve(rec.record_id, approved_by="self")  # self-approval invalid
        assert False, "global requires external approval"
    except SelfModError:
        pass


def test_selfmod_rollback():
    gov = SelfModificationGovernor(mission_id="m3")
    rec = gov.propose(proposed_change="p", rationale="r", triggering_evidence="e",
                      original_behavior="o", expected_improvement="i",
                      risk_analysis="low", affected_scope="project_local",
                      diff="-a\n+b", tests_or_validation="t",
                      rollback_path="git revert", approval_requirement="project_local")
    gov.approve(rec.record_id)
    gov.apply(rec.record_id)
    gov.rollback(rec.record_id)
    assert rec.status == SelfModState.ROLLED_BACK.value


def test_selfmod_dedup():
    gov = SelfModificationGovernor(mission_id="m4")
    a = gov.propose(proposed_change="same", rationale="r", triggering_evidence="e",
                    original_behavior="o", expected_improvement="i",
                    risk_analysis="low", affected_scope="project_local",
                    diff="-a\n+b", tests_or_validation="t",
                    rollback_path="rb", approval_requirement="project_local")
    b = gov.propose(proposed_change="same", rationale="r", triggering_evidence="e",
                    original_behavior="o", expected_improvement="i",
                    risk_analysis="low", affected_scope="project_local",
                    diff="-a\n+b", tests_or_validation="t",
                    rollback_path="rb", approval_requirement="project_local")
    assert a.record_id == b.record_id  # deduplicated


def test_checkpoint_resume_and_divergence():
    tmp = tempfile.mkdtemp()
    store = CheckpointStore(tmp)
    cp = MissionCheckpoint(mission_id="m1", project_id="p1", objective="build X",
                           current_phase="3", completed_work=["p1", "p2"],
                           next_safe_action="implement p3",
                           latest_verified_state="abc1234")
    store.save(cp)
    loaded = store.load("m1")
    assert loaded.objective == "build X"
    # divergence: head changed
    div = detect_divergence(loaded, current_head="def5678", current_branch="b",
                            current_files=[])
    assert "head" in div
    plan = resume_plan(loaded, div)
    assert plan["reuse_evidence"] is False
    assert "head" in plan["mark_stale_assumptions"]


def test_checkpoint_completed_not_restarted():
    tmp = tempfile.mkdtemp()
    store = CheckpointStore(tmp)
    cp = MissionCheckpoint(mission_id="done", project_id="p1", objective="done",
                           status=CheckpointStatus.COMPLETED.value,
                           next_safe_action="implement more")
    store.save(cp)
    loaded = store.load("done")
    plan = resume_plan(loaded, {})
    assert plan["next_action"] == "DO_NOT_RESTART_COMPLETED_MISSION"


def test_checkpoint_store_rejects_path_traversal_mission_id(tmp_path):
    """Caller-controlled mission IDs must not select files outside .capt/checkpoints."""
    store = CheckpointStore(str(tmp_path))
    checkpoint = MissionCheckpoint(mission_id="../../outside", project_id="p", objective="o")

    with pytest.raises(ValueError, match="mission_id"):
        store.save(checkpoint)
    with pytest.raises(ValueError, match="mission_id"):
        store.load("../outside")

    assert not (tmp_path / "outside.json").exists()


def test_antiloop_detects_repeat():
    g = AntiLoopGuard(max_repeats=2)
    s1 = g.repeated_verification("vsi:eq:math")
    s2 = g.repeated_verification("vsi:eq:math")
    s3 = g.repeated_verification("vsi:eq:math")  # 3rd > 2
    assert s1[0] is False and s2[0] is False
    assert s3[0] is True  # loop detected
    assert "Loop detected" in s3[1]
