"""Tests for v0.2 models, normalize, secrets, deduplicate, trust."""

import pytest

from capt_solo.memory.models import (
    AntiTokenPacket, ContextBuildResult, ContextItem, EdgeType, MemoryKind,
    SelectionStatus, StageResult, TrustState,
)
from capt_solo.memory.normalize import (
    extract_headings, normalize_content_hash, normalize_stage, normalize_text,
    sentence_segment,
)
from capt_solo.memory.secrets import screen, secret_screening_stage
from capt_solo.memory.deduplicate import detect_conflicts, find_duplicates, lexical_overlap
from capt_solo.memory.trust import (
    apply_transition, base_weight, can_transition, compute_trust, trust_from_kind,
)


# ----- models -----
def test_stage_result_rejection_sets_ok_false():
    r = StageResult(stage="x", ok=True)
    r.add_rejection("bad")
    assert r.ok is False
    assert "bad" in r.rejections


def test_memory_kind_from_tag():
    assert MemoryKind.from_tag("decision") == MemoryKind.DECISION
    assert MemoryKind.from_tag("nonsense") == MemoryKind.FACT


def test_edge_type_values():
    assert "contradicts" in EdgeType.values()
    assert "supersedes" in EdgeType.values()


def test_trust_state_enum():
    assert TrustState.INFERENCE.value == "inference"
    assert TrustState.VERIFIED_RESULT.value == "verified_result"


def test_antitoken_packet_to_dict():
    p = AntiTokenPacket(memory_id="m1", kind="decision", assertion="x")
    d = p.to_dict()
    assert d["memory_id"] == "m1"
    assert d["negation"] is False


def test_context_build_result_to_dict():
    r = ContextBuildResult(
        query="q", items=[ContextItem("m1", 0.5, True, "reason")],
        rendered="x", exclusions=[], conflicts=[], warnings=[],
        estimated_source_chars=100, estimated_compressed_chars=20,
        reduction_ratio=0.8, trace_id="t", config_snapshot={})
    d = r.to_dict()
    assert d["reduction_ratio"] == 0.8
    assert d["items"][0]["memory_id"] == "m1"


# ----- normalize -----
def test_normalize_text():
    assert normalize_text("  hello\n\t world  ") == "hello world"


def test_normalize_content_hash_stable():
    h1 = normalize_content_hash("Hello World", "ns", ("a", "b"))
    h2 = normalize_content_hash("hello world", "ns", ("b", "a"))
    assert h1 == h2  # case-insensitive + tag order independent


def test_normalize_content_hash_differs_by_ns():
    h1 = normalize_content_hash("x", "a", ())
    h2 = normalize_content_hash("x", "b", ())
    assert h1 != h2


def test_normalize_stage_empty():
    r = normalize_stage("   ")
    assert r.ok is False
    assert r.rejections


def test_normalize_stage_ok():
    r = normalize_stage("hello", "ns", ("t",))
    assert r.ok
    assert r.value["content_hash"]


def test_sentence_segment():
    s = sentence_segment("First. Second! Third?")
    assert s == ["First.", "Second!", "Third?"]


def test_extract_headings():
    h = extract_headings("# Title\nbody\n## Sub\nmore")
    assert h == ["Title", "Sub"]


# ----- secrets -----
def test_screen_detects_aws_key():
    has, reasons, redacted = screen("key AKIA1234567890ABCDEF here")
    assert has
    assert any("aws_access_key" in r for r in reasons)
    assert "AKIA1234567890ABCDEF" not in redacted


def test_screen_detects_password():
    has, reasons, redacted = screen("password=" + ("x" * 12))
    assert has
    assert "x" * 12 not in redacted


def test_screen_clean():
    has, reasons, redacted = screen("just some normal text about memory")
    assert has is False
    assert redacted == "just some normal text about memory"


def test_secret_screening_stage_rejects_by_default():
    r = secret_screening_stage("password=" + ("x" * 9))
    assert r.ok is False
    assert r.rejections


def test_secret_screening_stage_override():
    r = secret_screening_stage("password=" + ("x" * 9), allow_secrets=True)
    assert r.ok is True
    assert r.provenance_changes.get("secret_stored_with_override")


# ----- deduplicate -----
def test_lexical_overlap_identical():
    assert lexical_overlap("a b c", "a b c") == 1.0


def test_find_duplicates_exact():
    existing = [{"memory_id": "x", "content": "same text", "namespace": "ns",
                 "tags": ["t"], "metadata": {}}]
    r = find_duplicates("same text", "ns", ("t",), existing)
    assert r.ok
    assert any(m["kind"] == "exact" for m in r.value["matches"])


def test_find_duplicates_strong_overlap():
    # 13 shared tokens, 1 substituted -> Jaccard 13/15 = 0.866 >= 0.85
    common = " ".join(f"t{i}" for i in range(13))
    existing = [{"memory_id": "x", "content": common + " tail",
                 "namespace": "ns", "tags": [], "metadata": {}}]
    r = find_duplicates(common + " other", "ns", (), existing)
    assert any(m["kind"] == "strong_overlap" for m in r.value["matches"])


def test_detect_conflicts_opposite_polarity():
    existing = [{"memory_id": "x", "content": "SQLite is the right choice"}]
    conflicts = detect_conflicts("SQLite is NOT the right choice", existing)
    assert conflicts
    assert "x" in conflicts[0]["memory_id"]


# ----- trust -----
def test_base_weight_ordering():
    assert base_weight(TrustState.VERIFIED_RESULT) > base_weight(TrustState.INFERENCE)


def test_can_transition_allowed():
    assert can_transition(TrustState.INFERENCE, TrustState.HYPOTHESIS)
    assert not can_transition(TrustState.INFERENCE, TrustState.VERIFIED_RESULT)


def test_apply_transition_valid():
    assert apply_transition(TrustState.INFERENCE, TrustState.HYPOTHESIS) == TrustState.HYPOTHESIS


def test_apply_transition_invalid():
    with pytest.raises(ValueError):
        apply_transition(TrustState.INFERENCE, TrustState.VERIFIED_RESULT)


def test_compute_trust_inference_not_promoted():
    score, notes = compute_trust(TrustState.INFERENCE, confidence=0.9, verified=True)
    assert "explicit transition required" in " ".join(notes)
    # inference base weight, never auto-verified level
    assert score < base_weight(TrustState.VERIFIED_RESULT)


def test_compute_trust_penalties():
    s1, _ = compute_trust(TrustState.USER_FACT, contradiction=True)
    s2, _ = compute_trust(TrustState.USER_FACT)
    assert s1 < s2


def test_trust_from_kind():
    assert trust_from_kind(MemoryKind.DECISION) == TrustState.INSTRUCTION
    assert trust_from_kind(MemoryKind.HYPOTHESIS) == TrustState.HYPOTHESIS
    assert trust_from_kind(MemoryKind.SESSION_SUMMARY) == TrustState.GENERATED_SUMMARY
