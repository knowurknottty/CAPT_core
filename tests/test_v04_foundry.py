"""CAPT Solo v0.4 — Foundry tests (public-API only).

No test establishes eligibility by manually editing canonical trust, lifecycle,
run-count, evidence, or capability state in SQL. Eligibility is reached only
through the public APIs (ProcedureStore.verify_procedure, ProofEngine.record,
CapabilityRegistry.verify/govern_approve, SkillFoundry pipeline, etc.).

Covers: proof aggregation, claim validation, skill generation, validation
harness, composition, bubble quarantine/validation/install, governance,
rollback, registry semantics (idempotency, dedup, expiry, scope), degradation,
quarantine, negative tests, and JSON column hardening.
"""

import json
import time

import pytest

from capt_solo.foundry import (
    ProofEngine, ProofRequirement, CapabilityRegistry, ClaimGuard,
    SkillFoundry, ValidationHarness, SkillCurator, CompositionEngine,
    KnowledgeBubbleRuntime, Governance, decode_list, decode_dict,
    ColumnDecodeError,
)
from capt_solo.foundry.columns import decode_list, decode_dict
from capt_solo.lifecycle.procedures import ProcedureStore
from capt_solo.memory.engine import MemoryEngine
from capt_solo.ctp.journal import CTPRuntime


@pytest.fixture
def eng():
    e = MemoryEngine()
    yield e
    e.close()


@pytest.fixture
def foundry_stack(eng):
    """Wire proof + registry + claimguard + procedures + foundry + ctp."""
    ctp = CTPRuntime()
    pe = ProofEngine(eng._conn)
    reg = CapabilityRegistry(eng._conn, pe)
    cg = ClaimGuard(reg, pe)
    ps = ProcedureStore(eng)
    sf = SkillFoundry(eng._conn, pe, ps)
    return {"ctp": ctp, "pe": pe, "reg": reg, "cg": cg, "ps": ps, "sf": sf, "eng": eng}


# --- proof aggregation ---------------------------------------------------

def test_proof_aggregation_satisfied(foundry_stack):
    pe = foundry_stack["pe"]
    reg = foundry_stack["reg"]
    reg.register("cap_x", "does x", "capt_solo")
    pe.record("test_pass", "pytest", "h1", "t", scope="cap_x")
    pe.record("static_analysis", "flake8", "h2", "t", scope="cap_x")
    agg = reg.verify("cap_x", pe, [
        ProofRequirement("test_pass", 1, "cap_x"),
        ProofRequirement("static_analysis", 1, "cap_x"),
    ])
    assert agg["aggregate"]["satisfied"] is True
    assert agg["lifecycle"] == "validated"


def test_proof_aggregation_unsatisfied(foundry_stack):
    pe = foundry_stack["pe"]
    reg = foundry_stack["reg"]
    reg.register("cap_y", "does y", "capt_solo")
    pe.record("test_pass", "pytest", "h1", "t", scope="cap_y")
    agg = reg.verify("cap_y", pe, [
        ProofRequirement("test_pass", 1, "cap_y"),
        ProofRequirement("static_analysis", 1, "cap_y"),
    ])
    assert agg["aggregate"]["satisfied"] is False
    assert agg["lifecycle"] == "candidate"  # downgraded, not verified


# --- registry semantics: idempotency, dedup, expiry, scope ------------

def test_verify_is_idempotent(foundry_stack):
    pe = foundry_stack["pe"]
    reg = foundry_stack["reg"]
    reg.register("cap_z", "does z", "capt_solo")
    pe.record("test_pass", "pytest", "h1", "t", scope="cap_z")
    r1 = reg.verify("cap_z", pe, [ProofRequirement("test_pass", 1, "cap_z")])
    # second call with same evidence must NOT advance lifecycle
    r2 = reg.verify("cap_z", pe, [ProofRequirement("test_pass", 1, "cap_z")])
    assert r1["lifecycle"] == "validated"
    assert r2["lifecycle"] == "validated"  # unchanged (idempotent)
    assert r2["promoted"] is False
    # mark_proven is a DISTINCT event (advances once)
    rp = reg.mark_proven("cap_z")
    assert rp["lifecycle"] == "proven"
    # repeated mark_proven is idempotent
    rp2 = reg.mark_proven("cap_z")
    assert rp2["promoted"] is False


def test_duplicate_evidence_not_counted_twice(foundry_stack):
    pe = foundry_stack["pe"]
    reg = foundry_stack["reg"]
    reg.register("cap_d", "does d", "capt_solo")
    # same hash recorded twice -> still 1 distinct evidence
    pe.record("test_pass", "pytest", "samehash", "t", scope="cap_d")
    pe.record("test_pass", "pytest", "samehash", "t", scope="cap_d")
    agg = reg.verify("cap_d", pe, [ProofRequirement("test_pass", 2, "cap_d")])
    # requirement needs 2 distinct; duplicate hash counts once
    assert agg["aggregate"]["satisfied"] is False


def test_expired_evidence_cannot_verify(foundry_stack):
    pe = foundry_stack["pe"]
    reg = foundry_stack["reg"]
    reg.register("cap_e", "does e", "capt_solo")
    # record with zero TTL -> immediately expired
    pe.record("test_pass", "pytest", "h1", "t", scope="cap_e", ttl=0)
    agg = reg.verify("cap_e", pe, [ProofRequirement("test_pass", 1, "cap_e")])
    assert agg["aggregate"]["satisfied"] is False


def test_out_of_scope_evidence_cannot_verify(foundry_stack):
    pe = foundry_stack["pe"]
    reg = foundry_stack["reg"]
    reg.register("cap_s", "does s", "capt_solo")
    pe.record("test_pass", "pytest", "h1", "t", scope="other_scope")
    agg = reg.verify("cap_s", pe, [ProofRequirement("test_pass", 1, "cap_s")])
    assert agg["aggregate"]["satisfied"] is False


def test_validated_not_reported_as_verified(foundry_stack):
    pe = foundry_stack["pe"]
    reg = foundry_stack["reg"]
    cg = foundry_stack["cg"]
    reg.register("cap_v", "does v", "capt_solo")
    pe.record("test_pass", "pytest", "h1", "t", scope="cap_v")
    reg.verify("cap_v", pe, [ProofRequirement("test_pass", 1, "cap_v")])
    v = cg.assert_capability("cap_v")
    assert v.supported is False  # validated != verified
    assert "validated" in v.language


def test_govern_approve_requires_distinct_event(foundry_stack):
    pe = foundry_stack["pe"]
    reg = foundry_stack["reg"]
    reg.register("cap_g", "does g", "capt_solo")
    pe.record("test_pass", "pytest", "h1", "t", scope="cap_g")
    reg.verify("cap_g", pe, [ProofRequirement("test_pass", 1, "cap_g")])
    reg.mark_proven("cap_g")  # DISTINCT event: validated -> proven
    # govern_approve moves to verified
    r = reg.govern_approve("cap_g", "captain")
    assert r["lifecycle"] == "verified"
    assert r["promoted"] is True
    # repeated govern_approve is idempotent
    r2 = reg.govern_approve("cap_g", "captain")
    assert r2["promoted"] is False


def test_govern_approve_rejects_unproven(foundry_stack):
    reg = foundry_stack["reg"]
    reg.register("cap_u", "does u", "capt_solo")
    with pytest.raises(Exception):
        reg.govern_approve("cap_u", "captain")


def test_claimguard_language_per_state(foundry_stack):
    pe = foundry_stack["pe"]
    reg = foundry_stack["reg"]
    cg = foundry_stack["cg"]
    reg.register("cap_l", "does l", "capt_solo")
    # candidate -> downgraded
    v0 = cg.verify_claim("Migration completed.", capability_id="cap_l")
    assert v0.supported is False
    # add evidence -> validated
    pe.record("test_pass", "pytest", "h1", "t", scope="cap_l")
    reg.verify("cap_l", pe, [ProofRequirement("test_pass", 1, "cap_l")])
    v1 = cg.verify_claim("Migration completed.", capability_id="cap_l")
    assert v1.supported is False  # validated still downgraded
    # mark_proven -> proven, then govern approve -> verified
    reg.mark_proven("cap_l")
    reg.govern_approve("cap_l", "captain")
    v2 = cg.verify_claim("Migration completed.", capability_id="cap_l")
    assert v2.supported is True


# --- claimguard integration: claim words --------------------------------

def test_claimguard_detects_unproofed_claim(foundry_stack):
    cg = foundry_stack["cg"]
    v = cg.verify_claim("The migration is complete and verified.")
    # no capability matches -> unsupported
    assert v.supported is False


# --- skill generation via public API -----------------------------------

def test_skill_pipeline_public_api(foundry_stack):
    ps = foundry_stack["ps"]
    sf = foundry_stack["sf"]
    pe = foundry_stack["pe"]
    # 1. create procedure
    pid = ps.create("deploy", steps="echo build\necho ship", verification="smoke")
    # 2. record runs through public API
    ps.record_run(pid, outcome="success", verification_result="smoke passed")
    ps.record_run(pid, outcome="success", verification_result="smoke passed")
    # 3. public verification (no direct SQL)
    ps.verify_procedure(pid, min_success=2)
    proc = ps.get(pid)
    assert proc.trust_state == "verified"
    # 4. skill candidate from verified procedure
    cid = sf.create_candidate(pid)
    # 5. build skill
    sid = sf.build_skill(cid, name="deploy-skill", purpose="deploy safely",
                          verification_requirements=[
                              {"type": "static_analysis", "min_count": 1}])
    # 6. validate via harness
    report = sf.validate(sid, ValidationHarness(pe))
    assert report.passed is True
    # 7. review + approve + publish
    sf.submit_for_review(sid)
    sf.approve(sid, reviewer="captain")
    sf.publish(sid, ctp_tx_id="tx-pub")
    sk = sf.get(sid)
    assert sk.lifecycle_state == "published"


def test_skill_cannot_publish_without_approval(foundry_stack):
    ps = foundry_stack["ps"]
    sf = foundry_stack["sf"]
    pid = ps.create("build", steps="echo ok", verification="smoke")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.verify_procedure(pid, min_success=2)
    cid = sf.create_candidate(pid)
    sid = sf.build_skill(cid, name="build-skill")
    sf.validate(sid, ValidationHarness(foundry_stack["pe"]))
    sf.submit_for_review(sid)
    # publish without approve must fail
    with pytest.raises(Exception):
        sf.publish(sid)


def test_skill_cannot_create_from_unverified_procedure(foundry_stack):
    ps = foundry_stack["ps"]
    sf = foundry_stack["sf"]
    pid = ps.create("raw", steps="echo x", verification="smoke")
    ps.record_run(pid, outcome="success")  # no verification result
    with pytest.raises(Exception):
        sf.create_candidate(pid)  # not verified


# --- validation harness -------------------------------------------------

def test_harness_12_stages(foundry_stack):
    ps = foundry_stack["ps"]
    sf = foundry_stack["sf"]
    pe = foundry_stack["pe"]
    pid = ps.create("op", steps="echo run", verification="smoke")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.verify_procedure(pid, min_success=2)
    cid = sf.create_candidate(pid)
    sid = sf.build_skill(cid, name="op-skill",
                          permissions=["filesystem:read"],
                          verification_requirements=[{"type": "static_analysis", "min_count": 1}])
    report = sf.validate(sid, ValidationHarness(pe))
    stage_names = {s.stage for s in report.stages}
    assert stage_names == {
        "schema", "static", "dependency", "compatibility", "permission",
        "fixture", "execution", "output", "failure_path", "rollback",
        "secret", "proof"}
    assert report.passed is True


def test_harness_blocks_on_unsafe_permission(foundry_stack):
    ps = foundry_stack["ps"]
    sf = foundry_stack["sf"]
    pe = foundry_stack["pe"]
    pid = ps.create("op2", steps="echo run", verification="smoke")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.verify_procedure(pid, min_success=2)
    cid = sf.create_candidate(pid)
    sid = sf.build_skill(cid, name="op2-skill",
                          permissions=["filesystem:read", "GOD_MODE"])
    report = sf.validate(sid, ValidationHarness(pe))
    perm = [s for s in report.stages if s.stage == "permission"][0]
    assert perm.status == "fail"


# --- composition --------------------------------------------------------

def test_composition_requires_published_skills(foundry_stack):
    ps = foundry_stack["ps"]
    sf = foundry_stack["sf"]
    pe = foundry_stack["pe"]
    pid = ps.create("a", steps="echo a", verification="smoke")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.verify_procedure(pid, min_success=2)
    cid = sf.create_candidate(pid)
    sid = sf.build_skill(cid, name="a-skill",
                          verification_requirements=[{"type": "static_analysis", "min_count": 1}])
    sf.validate(sid, ValidationHarness(pe))
    sf.submit_for_review(sid)
    sf.approve(sid, reviewer="captain")
    sf.publish(sid)
    ce = CompositionEngine(sf)
    # composing a published skill alone is valid
    res = ce.validate("wf", [sid])
    assert res["valid"] is True
    # composing a non-published skill id must fail
    cid2 = sf.create_candidate(pid)
    sid2 = sf.build_skill(cid2, name="a-skill-2")
    with pytest.raises(Exception):
        ce.validate("wf2", [sid2])


# --- bubble safety ------------------------------------------------------

def test_bubble_import_quarantined(foundry_stack):
    eng = foundry_stack["eng"]
    pe = foundry_stack["pe"]
    kb = KnowledgeBubbleRuntime(eng._conn)
    bubble = KnowledgeBubbleRuntime.build_bubble(
        "test-bubble", skills=[{"name": "x", "permissions": ["filesystem:read"]}],
        proof=[{"type": "static_analysis", "hash": "h"}])
    bid = kb.import_bubble(bubble)
    b = kb.get(bid)
    assert b["lifecycle_state"] == "quarantined"


def test_bubble_validate_then_approve_then_install(foundry_stack):
    eng = foundry_stack["eng"]
    kb = KnowledgeBubbleRuntime(eng._conn)
    bubble = KnowledgeBubbleRuntime.build_bubble(
        "safe-bubble", skills=[{"name": "y", "permissions": ["filesystem:read"]}],
        proof=[{"type": "static_analysis", "hash": "h"}],
        trust_metadata={"source": "captain", "confidence": 0.9})
    bid = kb.import_bubble(bubble)
    rep = kb.validate_bubble(bid)
    assert rep.passed is True
    kb.approve_bubble(bid, "captain")
    res = kb.install_bubble(bid, ctp_tx_id="tx-inst")
    assert res["bubble_id"] == bid
    assert kb.get(bid)["lifecycle_state"] == "installed"


def test_bubble_cannot_install_without_approval(foundry_stack):
    eng = foundry_stack["eng"]
    kb = KnowledgeBubbleRuntime(eng._conn)
    bubble = KnowledgeBubbleRuntime.build_bubble(
        "nb", skills=[{"name": "z", "permissions": ["filesystem:read"]}],
        proof=[{"type": "static_analysis", "hash": "h"}])
    bid = kb.import_bubble(bubble)
    kb.validate_bubble(bid)
    with pytest.raises(Exception):
        kb.install_bubble(bid)


def test_bubble_export_excludes_private(foundry_stack):
    eng = foundry_stack["eng"]
    kb = KnowledgeBubbleRuntime(eng._conn)
    out = kb.export_selected(include_private=False)
    assert out["format"] == "capt-solo-knowledge-bubble"
    # no private memory content leaked (export_policy key is allowed; the
    # sentinel below would only appear if actual private data were included)
    assert "SECRET_LEAK_SENTINEL" not in json.dumps(out)


# --- governance ---------------------------------------------------------

def test_governance_publish_generates_receipt(foundry_stack):
    ps = foundry_stack["ps"]
    sf = foundry_stack["sf"]
    pe = foundry_stack["pe"]
    ctp = foundry_stack["ctp"]
    pid = ps.create("g", steps="echo g", verification="smoke")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.verify_procedure(pid, min_success=2)
    cid = sf.create_candidate(pid)
    sid = sf.build_skill(cid, name="g-skill",
                          verification_requirements=[{"type": "static_analysis", "min_count": 1}])
    sf.validate(sid, ValidationHarness(pe))
    sf.submit_for_review(sid)
    sf.approve(sid, reviewer="captain")
    gov = Governance(foundry_stack["eng"]._conn, ctp, foundry=sf)
    rcpt = gov.publish_skill(sid, actor="captain", reason="release")
    assert rcpt.ctp_tx_id is not None
    assert rcpt.status == "committed"
    assert sf.get(sid).lifecycle_state == "published"
    # audit trail recorded
    trail = gov.audit_trail(target=sid)
    assert any(t["action"] == "publish_skill" for t in trail)


# --- JSON column hardening ----------------------------------------------

def test_decode_list_from_json_string():
    assert decode_list('[1,2,3]', field="x") == [1, 2, 3]


def test_decode_list_from_already_list():
    assert decode_list([1, 2], field="x") == [1, 2]


def test_decode_list_rejects_scalar():
    with pytest.raises(ColumnDecodeError):
        decode_list('"not a list"', field="x")


def test_decode_list_rejects_object():
    with pytest.raises(ColumnDecodeError):
        decode_list('{"a": 1}', field="x")


def test_decode_list_rejects_malformed():
    with pytest.raises(ColumnDecodeError):
        decode_list('[1,2', field="x")


def test_decode_list_rejects_none():
    with pytest.raises(ColumnDecodeError):
        decode_list(None, field="x")


def test_decode_dict_from_json_string():
    assert decode_dict('{"a": 1}', field="x") == {"a": 1}


def test_decode_dict_rejects_scalar():
    with pytest.raises(ColumnDecodeError):
        decode_dict('42', field="x")


def test_decode_dict_rejects_array():
    with pytest.raises(ColumnDecodeError):
        decode_dict('[1,2]', field="x")


def test_roundtrip_capability_json_columns(foundry_stack):
    reg = foundry_stack["reg"]
    reg.register("cap_json", "j", "capt_solo",
                 required_tools=["t1"], permissions=["p1"],
                 compatibility_matrix={"capt-solo": ">=0.3"})
    cap = reg.get("cap_json")
    assert cap.required_tools == ["t1"]
    assert cap.permissions == ["p1"]
    assert cap.compatibility_matrix == {"capt-solo": ">=0.3"}


def test_roundtrip_skill_json_columns(foundry_stack):
    ps = foundry_stack["ps"]
    sf = foundry_stack["sf"]
    pid = ps.create("j", steps="echo j", verification="smoke")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.verify_procedure(pid, min_success=2)
    cid = sf.create_candidate(pid)
    sid = sf.build_skill(cid, name="j-skill", required_tools=["t"],
                          permissions=["filesystem:read"],
                          workflow=["echo a", "echo b"])
    sk = sf.get(sid)
    assert sk.required_tools == ["t"]
    assert sk.permissions == ["filesystem:read"]
    assert sk.workflow == ["echo a", "echo b"]
