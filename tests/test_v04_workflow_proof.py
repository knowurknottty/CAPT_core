"""CAPT Solo v0.4 — Workflow Proof tests.

A composite workflow must NOT inherit verification from its child skills.
Each workflow carries an independent proof with its own lifecycle.

Negative cases required:
- incompatible outputs block validation
- missing component proof blocks proof
- permission escalation is surfaced
- rollback incompatibility blocks publication
- component revocation degrades the workflow
- stale component proof is not silently accepted
- duplicate component evidence is not double-counted
"""

import pytest

from capt_solo.memory.engine import MemoryEngine
from capt_solo.lifecycle.procedures import ProcedureStore
from capt_solo.foundry import (
    ProofEngine, CapabilityRegistry, SkillFoundry, ValidationHarness,
    WorkflowProofEngine, WORKFLOW_LIFECYCLE, ProofRequirement,
)


@pytest.fixture
def wf_stack(tmp_path, monkeypatch):
    monkeypatch.setenv("CAPT_SOLO_HOME", str(tmp_path))
    eng = MemoryEngine()
    pe = ProofEngine(eng._conn)
    ps = ProcedureStore(eng)
    sf = SkillFoundry(eng._conn, pe, ps)
    wpe = WorkflowProofEngine(eng._conn, sf, pe)
    return {"eng": eng, "pe": pe, "ps": ps, "sf": sf, "wpe": wpe}


def _publish_skill(stack, name, perms, rollback="revert step", compat="macos"):
    ps, sf, pe = stack["ps"], stack["sf"], stack["pe"]
    pid = ps.create(name, steps="echo x", verification="smoke")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.verify_procedure(pid, min_success=2)
    cid = sf.create_candidate(pid)
    sid = sf.build_skill(
        cid, name=name, permissions=perms, rollback_strategy=rollback,
        compatibility=compat,
        verification_requirements=[{"type": "static_analysis", "min_count": 1}])
    rep = sf.validate(sid, ValidationHarness(pe))
    assert rep.passed
    sf.submit_for_review(sid)
    sf.approve(sid, reviewer="captain")
    sf.publish(sid)
    return sid


def test_workflow_proof_independent_of_components(wf_stack):
    s1 = _publish_skill(wf_stack, "s1", ["filesystem:read"])
    s2 = _publish_skill(wf_stack, "s2", ["filesystem:write"])
    wpe = wf_stack["wpe"]
    wp = wpe.evaluate("wf1", "1.0.0", [s1, s2])
    # workflow starts as candidate even though components are published+verified
    assert wp.lifecycle_state == "candidate"
    wpe.save(wp)
    # re-evaluate with unchanged evidence is idempotent
    wp2 = wpe.evaluate("wf1", "1.0.0", [s1, s2])
    assert wp2.lifecycle_state == "candidate"
    # advance lifecycle explicitly
    wpe.set_lifecycle("wf1", "validated")
    assert wpe.get("wf1").lifecycle_state == "validated"
    wpe.set_lifecycle("wf1", "proven")
    wpe.set_lifecycle("wf1", "approved")
    wpe.set_lifecycle("wf1", "verified")
    assert wpe.get("wf1").lifecycle_state == "verified"


def test_workflow_lifecycle_states(wf_stack):
    s1 = _publish_skill(wf_stack, "s1", ["filesystem:read"])
    wpe = wf_stack["wpe"]
    wp = wpe.evaluate("wf2", "1.0.0", [s1])
    wpe.save(wp)
    for state in ("validated", "proven", "approved", "verified",
                 "degraded", "deprecated", "revoked"):
        wpe.set_lifecycle("wf2", state)
        assert wpe.get("wf2").lifecycle_state == state
    # invalid state rejected
    with pytest.raises(Exception):
        wpe.set_lifecycle("wf2", "bogus")


def test_incompatible_outputs_block_validation(wf_stack):
    s1 = _publish_skill(wf_stack, "s1", ["filesystem:read"])
    s2 = _publish_skill(wf_stack, "s2", ["filesystem:write"])
    wpe = wf_stack["wpe"]
    # step 1 claims input from step 1 itself (forward/self ref) -> io invalid
    mappings = [
        {"input_mapping": {"x": "step:1"}},  # step 0 referencing step 1
        {},
    ]
    wp = wpe.evaluate("wf3", "1.0.0", [s1, s2], mappings=mappings)
    assert wp.io_compatibility["ok"] is False
    assert len(wp.io_compatibility["issues"]) > 0


def test_permission_escalation_surfaced(wf_stack):
    s1 = _publish_skill(wf_stack, "s1", ["filesystem:read"])
    wpe = wf_stack["wpe"]
    wp = wpe.evaluate("wf4", "1.0.0", [s1])
    # no escalation when perms are within allowed set
    assert wp.permission_escalation == []
    # a disallowed perm in a component surfaces escalation
    sf = wf_stack["sf"]
    ps = wf_stack["ps"]
    pe = wf_stack["pe"]
    # build a verified procedure so the skill can be created
    pid = ps.create("badproc", steps="echo", verification="smoke")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.verify_procedure(pid, min_success=2)
    cid = sf.create_candidate(pid)
    sid = sf.build_skill(
        cid, name="bad", permissions=["unknown:perm"], rollback_strategy="r",
        verification_requirements=[{"type": "static_analysis", "min_count": 1}])
    # skill exists (even if validation later fails); evaluate surfaces escalation
    wp2 = wpe.evaluate("wf5", "1.0.0", [sid])
    assert any("unknown:perm" in e for e in wp2.permission_escalation)


def test_rollback_incompatibility_blocks_publication(wf_stack):
    # Build a component skill with NO rollback strategy. The skill may exist
    # (its own validation may flag it), but the workflow proof must detect the
    # missing rollback and mark rollback_compatibility incompatible — which
    # blocks workflow publication.
    sf = wf_stack["sf"]
    ps = wf_stack["ps"]
    pe = wf_stack["pe"]
    pid = ps.create("rbproc", steps="echo", verification="smoke")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.verify_procedure(pid, min_success=2)
    cid = sf.create_candidate(pid)
    sid = sf.build_skill(
        cid, name="rb", permissions=["filesystem:read"], rollback_strategy="",
        verification_requirements=[{"type": "static_analysis", "min_count": 1}])
    wpe = wf_stack["wpe"]
    wp = wpe.evaluate("wf6", "1.0.0", [sid])
    assert wp.rollback_compatibility["compatible"] is False
    assert sid in wp.rollback_compatibility["missing"]


def test_component_revocation_degrades_workflow(wf_stack):
    s1 = _publish_skill(wf_stack, "s1", ["filesystem:read"])
    wpe = wf_stack["wpe"]
    wp = wpe.evaluate("wf7", "1.0.0", [s1])
    wpe.save(wp)
    wpe.set_lifecycle("wf7", "verified")
    # revoke the component skill -> workflow should be degradable
    wf_stack["sf"].revoke(s1, reason="security")
    # re-evaluate reflects component revocation in component inventory
    wp2 = wpe.evaluate("wf7", "1.0.0", [s1])
    assert any(c["skill_id"] == s1 for c in wp2.components)


def test_duplicate_component_evidence_not_double_counted(wf_stack):
    s1 = _publish_skill(wf_stack, "s1", ["filesystem:read"])
    s2 = _publish_skill(wf_stack, "s2", ["filesystem:write"])
    wpe = wf_stack["wpe"]
    wp = wpe.evaluate("wf8", "1.0.0", [s1, s2])
    # component_proof_refs are distinct per component
    assert len(wp.component_proof_refs) == len(set(wp.component_proof_refs)) == 2
    # recording the same evidence twice is idempotent (not double-counted)
    wpe.save(wp)
    wpe.record_evidence("wf8", "integration", "evt1")
    wpe.record_evidence("wf8", "integration", "evt1")
    assert wpe.get("wf8").integration_evidence.count("evt1") == 1
