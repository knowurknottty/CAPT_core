"""CAPT Solo v0.4 — Capability Degradation tests.

Verifies the 12 explicit degradation reason codes, structured degradation
records, scoped ClaimGuard language (macOS-only degradation != global
revoke), and that degradation moves the capability to the correct lifecycle.
"""

import pytest

from capt_solo.memory.engine import MemoryEngine
from capt_solo.foundry import (
    ProofEngine, CapabilityRegistry, ClaimGuard, ProofRequirement,
    DEGRADATION_REASONS,
)


@pytest.fixture
def reg_stack(tmp_path, monkeypatch):
    monkeypatch.setenv("CAPT_SOLO_HOME", str(tmp_path))
    eng = MemoryEngine()
    pe = ProofEngine(eng._conn)
    reg = CapabilityRegistry(eng._conn, pe)
    cg = ClaimGuard(reg, pe)
    return {"eng": eng, "pe": pe, "reg": reg, "cg": cg}


def _verified_cap(reg, pe, cid):
    reg.register(cid, "does x", "capt_solo")
    pe.record("test_pass", "pytest", "h1", "t", scope=cid)
    reg.verify(cid, pe, [ProofRequirement("test_pass", 1, cid)])
    reg.mark_proven(cid)
    reg.govern_approve(cid, approver="captain")
    return cid


def test_all_12_reason_codes_defined():
    assert set(DEGRADATION_REASONS.keys()) == {
        "dependency_missing", "environment_changed", "proof_expired",
        "compatibility_failed", "security_revoked", "manual_disable",
        "superseded", "verification_failed", "component_degraded",
        "tool_contract_changed", "permission_policy_changed",
        "artifact_missing",
    }


def test_degrade_records_structured_record(reg_stack):
    reg = reg_stack["reg"]
    cid = _verified_cap(reg, reg_stack["pe"], "cap_d")
    rec = reg.degrade(
        cid, "proof_expired",
        explanation="evidence older than TTL",
        affected_scope="global",
        triggering_evidence="evt:h1",
        actor="captain",
        remediation="re-run verification")
    assert rec["reason"] == "proof_expired"
    assert rec["resulting_state"] == "degraded"
    assert rec["affected_scope"] == "global"
    assert rec["triggering_evidence"] == "evt:h1"
    # capability now degraded
    cap = reg.get(cid)
    assert cap.lifecycle == "degraded"
    assert cap.degradation_state == "proof_expired"
    # record retrievable
    recs = reg.get_degradations(cid)
    assert len(recs) == 1
    assert recs[0]["reason"] == "proof_expired"


def test_security_revoked_moves_to_revoked(reg_stack):
    reg = reg_stack["reg"]
    cid = _verified_cap(reg, reg_stack["pe"], "cap_sec")
    reg.degrade(cid, "security_revoked", actor="captain")
    assert reg.get(cid).lifecycle == "revoked"
    assert reg.get(cid).degradation_state == "security_revoked"


def test_unknown_reason_rejected(reg_stack):
    reg = reg_stack["reg"]
    cid = _verified_cap(reg, reg_stack["pe"], "cap_x")
    with pytest.raises(Exception):
        reg.degrade(cid, "bogus_reason")


def test_scoped_degradation_language_macos_not_global(reg_stack):
    reg = reg_stack["reg"]
    cg = reg_stack["cg"]
    cid = _verified_cap(reg, reg_stack["pe"], "cap_mac")
    reg.degrade(cid, "compatibility_failed",
                affected_scope="macos",
                explanation="fails on macOS only")
    v = cg.verify_claim("Task complete and verified.", capability_id=cid)
    assert v.supported is False
    # must NOT say globally revoked
    assert "not globally revoked" in v.language
    assert "macos" in v.language.lower()


def test_global_degradation_language(reg_stack):
    reg = reg_stack["reg"]
    cg = reg_stack["cg"]
    cid = _verified_cap(reg, reg_stack["pe"], "cap_g")
    reg.degrade(cid, "manual_disable", affected_scope="global",
                explanation="disabled by operator")
    v = cg.verify_claim("Task complete and verified.", capability_id=cid)
    assert v.supported is False
    assert "degraded (reason: manual_disable)" in v.language


def test_degradation_persists_across_reload(reg_stack, tmp_path, monkeypatch):
    reg = reg_stack["reg"]
    cid = _verified_cap(reg, reg_stack["pe"], "cap_p")
    reg.degrade(cid, "superseded", affected_scope="global")
    reg_stack["eng"].close()
    # reopen
    monkeypatch.setenv("CAPT_SOLO_HOME", str(tmp_path))
    eng2 = MemoryEngine()
    reg2 = CapabilityRegistry(eng2._conn, ProofEngine(eng2._conn))
    cap = reg2.get(cid)
    assert cap.lifecycle == "degraded"
    assert cap.degradation_state == "superseded"
    recs = reg2.get_degradations(cid)
    assert recs[0]["reason"] == "superseded"
    eng2.close()
