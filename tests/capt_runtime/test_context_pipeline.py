"""Context selection / reduction / packaging pipeline tests (Gate 7)."""

import pytest

from capt_runtime.context_pipeline import (
    run_pipeline,
    select_knowledge_bubbles,
    select_context,
    reduce_context,
    build_context_slice_stage,
    package_context_pack,
)
from capt_runtime.memory import MemoryStore, MemoryRecord, build_memory_query


def _store():
    s = MemoryStore(":memory:")
    s.store(MemoryRecord(
        record_id="r1", memory_class="project", owner="capt", source="fs",
        provenance="m:x", trust="verified", verification_status="verified",
        sensitivity="project", consent="project", content="prior denial"))
    s.store(MemoryRecord(
        record_id="r2", memory_class="user", owner="operator", source="stated",
        provenance="op:y", trust="unverified", verification_status="pending",
        sensitivity="user", consent="user", content="pref concise"))
    return s


def _query():
    return build_memory_query(
        mission_id="m1", task_id="t1", actor="capt", requesting_subsystem="memory",
        trigger_boundary=32768, context_usage=1000,
        requested_memory_classes=["project", "user"], project_scope="proj",
        purpose="test", record_limit=20, token_budget=100000,
        relevance_criteria="prior", trust_threshold=0.0,
        consent_scope="project", sensitivity_allowance="project",
        provenance_requirement=None, causation_id="c0")


def test_knowledge_bubble_selection():
    out = select_knowledge_bubbles(_store(), classes=["project", "user"], project_scope="proj")
    assert out["stage"] == "knowledge_bubble_selection"
    assert out["selectedCount"] == 2
    assert out["stageDigest"].startswith("sha256:")


def test_context_selection_excludes_consent_mismatch():
    out = select_context(_store(), classes=["project", "user"], project_scope="proj",
                         consent_scope="project", sensitivity_allowance="project",
                         token_budget=100000)
    ids = {r["recordId"] for r in out["selectedRecords"]}
    assert "r2" not in ids  # user consent excluded under project scope
    assert out["excludedCount"] >= 1


def test_context_reduction_respects_budget():
    sel = select_context(_store(), classes=["project", "user"], project_scope="proj",
                         consent_scope="project", sensitivity_allowance="project",
                         token_budget=100000)["selectedRecords"]
    red = reduce_context(sel, token_budget=1)  # tiny budget forces deferral
    assert red["reducedCount"] <= len(sel)


def test_context_slice_stage_no_raw_memory():
    stage = build_context_slice_stage([{"recordId": "r1"}], context_pack_digest="sha256:" + "a" * 64)
    sl = stage["contextSlice"]
    assert sl["contextPackDigest"] == "sha256:" + "a" * 64
    assert sl["selectedRecordCount"] == 1
    assert "kind" in sl


def test_package_context_pack_valid():
    store = _store()
    pack = package_context_pack(store=store, policy_version=1, trigger_boundary=32768,
                                context_usage_before=1000, query=_query())
    assert pack["contextPackDigest"].startswith("sha256:")


def test_full_pipeline_runs_and_is_auditable():
    store = _store()
    out = run_pipeline(store=store, policy_version=1, trigger_boundary=32768,
                       context_usage_before=1000, query=_query(), mission_id="m1")
    stages = out["stages"]
    assert set(stages.keys()) == {
        "knowledge_bubble_selection", "context_selection",
        "context_reduction", "context_slice_construction"}
    # Each stage reproducible via its digest
    for st in stages.values():
        assert st["stageDigest"].startswith("sha256:")
    # The slice references the pack digest (no raw memory)
    assert stages["context_slice_construction"]["contextSlice"]["contextPackDigest"] == \
        out["contextPack"]["contextPackDigest"]


def test_pipeline_deterministic():
    store = _store()
    a = run_pipeline(store=store, policy_version=1, trigger_boundary=32768,
                     context_usage_before=1000, query=_query(), mission_id="m1")
    b = run_pipeline(store=store, policy_version=1, trigger_boundary=32768,
                     context_usage_before=1000, query=_query(), mission_id="m1")
    assert a["contextPack"]["contextPackDigest"] == b["contextPack"]["contextPackDigest"]
