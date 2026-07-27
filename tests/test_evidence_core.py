"""Tests for Evidence Engine core, invalidation, reuse, and proof graph (Phases 1-4)."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from capt_solo.evidence import (
    EvidenceRecord, EvidenceClaim, EvidenceSource, EvidenceClass, EvidenceStatus,
    EvidenceScope, EvidenceBundle, EvidenceQuery, EvidenceDecision,
    InvalidationEvent, InvalidationReason, scan_invalidation, InvalidationGraph,
    EvidenceReuseEngine, ReuseOutcome, ProofGraph,
)
from capt_solo.evidence.core import new_record_id

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _rec(claim_id, cls, status=EvidenceStatus.CURRENT.value, scope=EvidenceScope.PROJECT.value,
         paths=None, project="capt-solo"):
    claim = EvidenceClaim(claim_id=claim_id, statement=f"claim {claim_id}", claim_type="behavior")
    src = EvidenceSource(source_type="test", reference="tests/x.py", repository=REPO,
                         project_id=project, branch="integration/full-public-architecture",
                         head_commit="a0124c1", source_paths=paths or ["capt_solo/engines/mathematics.py"])
    return EvidenceRecord(record_id=new_record_id(), claim=claim, evidence_class=cls,
                          source=src, status=status, scope=scope, project_id=project,
                          repository_identity=REPO)


def test_evidence_record_creation_and_provenance():
    r = _rec("claim-math", EvidenceClass.TEST_RESULT.value)
    r.provenance_chain = ["eng:v1", "vsi:eq"]
    d = r.to_dict()
    assert d["record_id"] == r.record_id
    assert d["provenance_chain"] == ["eng:v1", "vsi:eq"]
    r2 = EvidenceRecord.from_dict(d)
    assert r2.claim.claim_id == "claim-math"
    assert r2.provenance_chain == ["eng:v1", "vsi:eq"]


def test_evidence_query_by_claim():
    b = EvidenceBundle(bundle_id="b1")
    b.add(_rec("c1", EvidenceClass.TEST_RESULT.value))
    b.add(_rec("c1", EvidenceClass.STATIC_ANALYSIS.value))
    b.add(_rec("c2", EvidenceClass.TEST_RESULT.value))
    assert len(b.by_claim("c1")) == 2
    assert len(b.current_for_claim("c1")) == 2


def test_invalidation_scoped_docs_not_dsp():
    evs = [
        _rec("dsp", EvidenceClass.TEST_RESULT.value, paths=["capt_solo/engines/mathematics.py"]),
        _rec("docs", EvidenceClass.TEST_RESULT.value, paths=["docs/architecture.md"]),
    ]
    # docs/architecture.md changed -> only docs evidence (sourced from it) affected
    ev = scan_invalidation(InvalidationReason.WORKING_TREE_PATH_CHANGED.value,
                           ["docs/architecture.md"], evs)
    assert "docs" in [r.claim.claim_id for r in evs if r.record_id in ev.affected_evidence_ids]
    assert "dsp" in [r.claim.claim_id for r in evs if r.record_id in ev.unaffected_evidence_ids]


def test_invalidation_head_full():
    evs = [_rec("a", EvidenceClass.TEST_RESULT.value), _rec("b", EvidenceClass.BUILD_RESULT.value)]
    ev = scan_invalidation(InvalidationReason.HEAD_CHANGED.value, ["any"], evs)
    assert set(ev.affected_evidence_ids) == {r.record_id for r in evs}
    assert ev.invalidation_scope == "full"


def test_invalidation_lockfile_full():
    evs = [_rec("build", EvidenceClass.BUILD_RESULT.value), _rec("doc", EvidenceClass.TEST_RESULT.value, paths=["docs/x.md"])]
    ev = scan_invalidation(InvalidationReason.DEPENDENCY_LOCKFILE_CHANGED.value, ["requirements.txt"], evs)
    assert set(ev.affected_evidence_ids) == {r.record_id for r in evs}


def test_reuse_when_equivalent():
    eng = EvidenceReuseEngine()
    eng.add(_rec("claim-x", EvidenceClass.TEST_RESULT.value))
    res = eng.decide(claim_id="claim-x", vsi_state="equivalent")
    assert res.outcome == ReuseOutcome.REUSE_CURRENT_EVIDENCE
    assert res.decision.action == "reuse_current_evidence"
    assert "No relevant state change" in res.decision.reason


def test_reuse_repeated_guard_no_rerun():
    eng = EvidenceReuseEngine()
    eng.add(_rec("claim-x", EvidenceClass.TEST_RESULT.value))
    r1 = eng.decide(claim_id="claim-x", vsi_state="equivalent")
    r2 = eng.decide(claim_id="claim-x", vsi_state="equivalent")
    assert r1.outcome == r2.outcome == ReuseOutcome.REUSE_CURRENT_EVIDENCE


def test_reuse_docs_change_keeps_dsp_current():
    eng = EvidenceReuseEngine()
    eng.add(_rec("dsp", EvidenceClass.TEST_RESULT.value, paths=["capt_solo/engines/mathematics.py"]))
    eng.add(_rec("docs", EvidenceClass.TEST_RESULT.value, paths=["docs/foo.md"]))
    # docs file changed; ask about dsp claim -> should reuse (unaffected)
    res = eng.decide(claim_id="dsp", vsi_state="changed",
                     invalidation_reason=InvalidationReason.WORKING_TREE_PATH_CHANGED.value,
                     changed_paths=["docs/foo.md"])
    assert res.outcome == ReuseOutcome.REUSE_CURRENT_EVIDENCE


def test_reuse_insufficient_when_no_evidence():
    eng = EvidenceReuseEngine()
    res = eng.decide(claim_id="missing", vsi_state="equivalent")
    assert res.outcome == ReuseOutcome.EVIDENCE_INSUFFICIENT


def test_proof_graph_traversal_and_cycle():
    g = ProofGraph()
    g.add_node("ev1", "evidence", "ev1")
    g.add_node("claim1", "claim", "claim1")
    g.add_node("claim2", "claim", "claim2")
    g.link("ev1", "claim1")
    g.link("claim1", "claim2")
    assert "claim1" in g.what_supports_claim("claim2")
    assert "claim2" in g.what_depends_on("ev1")
    assert g.cycle_free() is True
    # introduce a cycle
    g.link("claim2", "ev1")
    assert g.cycle_free() is False


def test_invalidation_graph_transitive():
    ig = InvalidationGraph()
    ev = scan_invalidation(InvalidationReason.SOURCE_EVIDENCE_DELETED.value, ["x"], [])
    ig.record(ev)
    dep_map = {"child": ["parent"], "parent": []}
    full = ig.transitive_invalidations(["parent"], dep_map)
    assert set(full) == {"parent", "child"}
