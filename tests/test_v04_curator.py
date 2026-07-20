"""CAPT Solo v0.4 — Skill Curator tests.

Verifies deterministic curation: duplicate detection, overlap detection,
unsafe permission detection, missing verification, broken compatibility,
obsolete state. The curator never rewrites skills; it only reports.
"""

import pytest

from capt_solo.memory.engine import MemoryEngine
from capt_solo.foundry import (
    ProofEngine, CapabilityRegistry, SkillFoundry, SkillCurator,
    ValidationHarness,
)
from capt_solo.lifecycle.procedures import ProcedureStore


@pytest.fixture
def cur_stack(tmp_path, monkeypatch):
    monkeypatch.setenv("CAPT_SOLO_HOME", str(tmp_path))
    eng = MemoryEngine()
    pe = ProofEngine(eng._conn)
    reg = CapabilityRegistry(eng._conn, pe)
    ps = ProcedureStore(eng)
    sf = SkillFoundry(eng._conn, pe, ps)
    cur = SkillCurator(sf)
    return {"eng": eng, "pe": pe, "reg": reg, "ps": ps, "sf": sf, "cur": cur}


def _build_skill(sf, ps, pe, name, trigger="", purpose="", perms=None,
                 compat="capt-solo>=0.3", verify=None, publish=True):
    pid = ps.create("op", steps="echo x", verification="smoke")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.verify_procedure(pid, min_success=2)
    cid = sf.create_candidate(pid)
    sid = sf.build_skill(
        cid, name=name, trigger=trigger, purpose=purpose,
        permissions=perms or ["filesystem:read"],
        compatibility=compat,
        verification_requirements=verify if verify is not None
        else [{"type": "static_analysis", "min_count": 1}])
    sf.validate(sid, ValidationHarness(pe))
    if publish:
        sf.submit_for_review(sid)
        sf.approve(sid, reviewer="captain")
        sf.publish(sid, ctp_tx_id="tx")
    return sid


def test_curate_empty(cur_stack):
    findings = cur_stack["cur"].curate()
    assert findings == []


def test_curate_detects_duplicate(cur_stack):
    sf = cur_stack["sf"]
    ps = cur_stack["ps"]
    pe = cur_stack["pe"]
    # two skills with identical name + content -> same content_hash
    _build_skill(sf, ps, pe, "dup", trigger="t", purpose="p")
    _build_skill(sf, ps, pe, "dup", trigger="t", purpose="p")
    findings = cur_stack["cur"].curate()
    kinds = [f.kind for f in findings]
    assert "duplicate" in kinds
    dup = [f for f in findings if f.kind == "duplicate"]
    assert dup[0].severity == "critical"


def test_curate_detects_overlap(cur_stack):
    sf = cur_stack["sf"]
    ps = cur_stack["ps"]
    pe = cur_stack["pe"]
    _build_skill(sf, ps, pe, "ov-a", trigger="same", purpose="same")
    _build_skill(sf, ps, pe, "ov-b", trigger="same", purpose="same")
    findings = cur_stack["cur"].curate()
    assert any(f.kind == "overlap" for f in findings)


def test_curate_detects_unsafe_permission(cur_stack):
    sf = cur_stack["sf"]
    ps = cur_stack["ps"]
    pe = cur_stack["pe"]
    # build + validate (fails validation) but skill still exists for curation
    _build_skill(sf, ps, pe, "bad-perm", perms=["unknown:perm"], publish=False)
    findings = cur_stack["cur"].curate()
    unsafe = [f for f in findings if f.kind == "unsafe_perm"]
    assert unsafe
    assert unsafe[0].severity == "critical"


def test_curate_detects_missing_verify(cur_stack):
    sf = cur_stack["sf"]
    ps = cur_stack["ps"]
    pe = cur_stack["pe"]
    _build_skill(sf, ps, pe, "no-verify", verify=[], publish=False)
    findings = cur_stack["cur"].curate()
    assert any(f.kind == "missing_verify" for f in findings)


def test_curate_detects_obsolete(cur_stack):
    sf = cur_stack["sf"]
    ps = cur_stack["ps"]
    pe = cur_stack["pe"]
    sid = _build_skill(sf, ps, pe, "old-skill")
    sf.deprecate(sid)
    findings = cur_stack["cur"].curate()
    assert any(f.kind == "obsolete" for f in findings)


def test_recommend_structure(cur_stack):
    sf = cur_stack["sf"]
    ps = cur_stack["ps"]
    pe = cur_stack["pe"]
    _build_skill(sf, ps, pe, "bad", perms=["unknown:perm"], publish=False)
    rec = cur_stack["cur"].recommend()
    assert "total" in rec
    assert "critical" in rec
    assert "warnings" in rec
    assert "info" in rec
    assert rec["action_required"] is True
