import json
import os
import sys
import threading
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from capt_solo.continuity import (  # noqa: E402
    ContinuityError, EvidenceGraph, ReceiptChain, build_pack_from_providers,
    evaluate_pack, load_policy,
)
from capt_solo.continuity.graph import EvidenceNode  # noqa: E402
from capt_solo.evidence import CheckpointStore, MissionCheckpoint  # noqa: E402
from capt_solo.evidence.providers import OperationalEvidence, StaticProvider  # noqa: E402
from capt_solo.memory.engine import MemoryEngine  # noqa: E402
from capt_solo.evidence.providers import MemoryProvider, MissionProvider  # noqa: E402


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POLICY = load_policy(os.path.join(ROOT, "architecture", "cve", "continuity-v0.2.yaml"))
NOW = datetime(2026, 7, 28, tzinfo=timezone.utc)


def _provider(items):
    return StaticProvider("test-provider", "1", NOW.isoformat(), "verified", items)


def _pack(providers):
    return build_pack_from_providers(
        "p1", "test", "C1", "test", [{"role": "operator", "identity": "a"},
        {"role": "reviewer", "identity": "b"}], [{"claim_id": "c", "statement": "x"}],
        POLICY["policy_id"], providers, created_at=NOW.isoformat())


def test_provider_graph_and_evaluation_are_repeatable():
    provider = _provider([{"evidence_id": "e1", "kind": "test", "status": "verified",
                           "timestamp": NOW.isoformat(), "confidence": 1.0}])
    pack = _pack([provider])
    assert evaluate_pack(pack, POLICY, NOW) == evaluate_pack(pack, POLICY, NOW)
    assert pack.metadata["evidence_graph"]["nodes"][0]["node_id"] == "e1"


def test_graph_rejects_missing_provider_duplicate_orphan_cycle_and_bad_time():
    with pytest.raises(ContinuityError): EvidenceGraph.from_providers([])
    duplicate = _provider([{"evidence_id": "same"}, {"evidence_id": "same"}])
    with pytest.raises(ContinuityError): EvidenceGraph.from_providers([duplicate])
    orphan = _provider([{"evidence_id": "a", "dependencies": ["missing"]}])
    with pytest.raises(ContinuityError): EvidenceGraph.from_providers([orphan])
    cycle = _provider([{"evidence_id": "a", "dependencies": ["b"]}, {"evidence_id": "b", "dependencies": ["a"]}])
    with pytest.raises(ContinuityError): EvidenceGraph.from_providers([cycle])
    bad_time = _provider([{"evidence_id": "time", "timestamp": "not-a-time"}])
    with pytest.raises(ContinuityError): EvidenceGraph.from_providers([bad_time])


def test_receipt_chain_is_append_only_and_detects_corruption(tmp_path):
    chain = ReceiptChain(tmp_path / "receipts.jsonl")
    first = chain.append({"receipt_version": "0.2", "pack_id": "one"})
    second = chain.append({"receipt_version": "0.2", "pack_id": "two"})
    assert second["previous_receipt_digest"]
    assert chain.verify() == {"valid": True, "entries": 2}
    path = tmp_path / "receipts.jsonl"
    path.write_text(json.dumps({**first, "chain_digest": "bad"}) + "\n")
    assert chain.verify()["valid"] is False


def test_receipt_chain_handles_concurrent_local_appends(tmp_path):
    chain = ReceiptChain(tmp_path / "receipts.jsonl")
    threads = [threading.Thread(target=chain.append, args=({"pack_id": str(i)},)) for i in range(12)]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    assert chain.verify() == {"valid": True, "entries": 12}


def test_mission_provider_uses_checkpoint_boundary(tmp_path):
    store = CheckpointStore(str(tmp_path))
    store.save(MissionCheckpoint(mission_id="m1", project_id="p", objective="o", timestamp=NOW.isoformat()))
    evidence = MissionProvider(store).evidence()
    assert evidence[0].kind == "mission_created"
    assert evidence[0].detail["checkpoint_digest"].startswith("sha256:")
    with pytest.raises(ValueError):
        store.record_event("m1", "invented-event")


def test_memory_provider_uses_public_non_content_status(tmp_path):
    engine = MemoryEngine(tmp_path / "memory.db")
    try:
        engine.store("private content", namespace="n")
        evidence = MemoryProvider(engine).evidence()[0]
        assert evidence.status == "verified"
        assert "private content" not in json.dumps(evidence.to_dict())
        assert evidence.detail["restore_capability"] is True
    finally:
        engine.close()


def test_block_explanation_has_clauses_path_and_remediation():
    pack = _pack([]) if False else _pack([_provider([])])
    result = evaluate_pack(pack, POLICY, NOW)
    explanation = result["explanations"][0]
    assert explanation["violated_clauses"]
    assert explanation["graph_path"] == ["graph:missing-evidence"]
    assert explanation["recommended_remediation"]


def test_clock_skew_and_provider_version_mismatch_block():
    future = _provider([{"evidence_id": "future", "timestamp": "2026-07-29T00:00:00+00:00"}])
    result = evaluate_pack(_pack([future]), POLICY, NOW)
    assert any(item["code"] == "clock_skew" for item in result["findings"])
    pack = _pack([_provider([{"evidence_id": "versioned"}])])
    pack.metadata["expected_provider_versions"] = {"StaticProvider:0": "different"}
    result = evaluate_pack(pack, POLICY, NOW)
    assert any(item["code"] == "provider_version_mismatch" for item in result["findings"])


def test_large_pack_is_sorted_and_has_stable_digest():
    provider = _provider([{"evidence_id": "e-%03d" % i} for i in range(300, 0, -1)])
    first, second = EvidenceGraph.from_providers([provider]), EvidenceGraph.from_providers([provider])
    assert first.to_dict() == second.to_dict()
    assert first.nodes()[0].node_id == "e-001"
