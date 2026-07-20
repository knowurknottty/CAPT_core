"""Focused coverage tests for AntiToken render/validate and trust compute branches."""

import json

import pytest

from capt_solo.memory.antitoken import estimate_reduction, extract, render, validate
from capt_solo.memory.models import AntiTokenPacket, TrustState
from capt_solo.memory.trust import base_weight, compute_trust


def _full_packet() -> AntiTokenPacket:
    return AntiTokenPacket(
        memory_id="m1", kind="decision", assertion="Use SQLite for storage.",
        subject="SQLite", action="use", obj="storage",
        constraints=["must be portable", "never use network"],
        rationale=["because offline", "to avoid deps"],
        evidence_refs=["test_abc", "ctp_xyz"],
        confidence=0.96, provenance_refs=["user"],
        temporal_scope="2026", status="active",
        contradictions=["mem_old"], supersedes=["mem_old2"],
        unresolved_questions=["is it fast enough?"],
        ctp_refs=["ctp_1"], negation=False, uncertainty=False,
        security_warning=False, destructive_warning=False)


def test_render_text_full_packet():
    pkt = _full_packet()
    out = render(pkt, "text")
    assert "Use SQLite for storage." in out
    assert "constraints:" in out
    assert "rationale:" in out
    assert "evidence:" in out
    assert "contradicts:" in out
    assert "supersedes:" in out
    assert "open:" in out


def test_render_text_negation_uncertainty_security():
    pkt = AntiTokenPacket(
        memory_id="m", kind="fact", assertion="Do NOT delete the key.",
        negation=True, uncertainty=True, security_warning=True,
        destructive_warning=True)
    out = render(pkt, "text")
    assert "! NEGATED" in out
    assert "? UNCERTAIN" in out
    assert "!! SECURITY WARNING" in out
    assert "!! DESTRUCTIVE ACTION" in out


def test_render_json_full_packet():
    pkt = _full_packet()
    d = json.loads(render(pkt, "json"))
    assert d["constraints"] == ["must be portable", "never use network"]
    assert d["evidence_refs"] == ["test_abc", "ctp_xyz"]


def test_render_model_neutral_full_packet():
    pkt = _full_packet()
    out = render(pkt, "model_neutral")
    assert "constraints=" in out
    assert "rationale=" in out
    assert "evidence=" in out
    assert "contradicts=" in out
    assert "supersedes=" in out


def test_validate_evidence_preserved():
    mem = {"memory_id": "m1", "content": "Use SQLite. evidence test_abc supports it.",
           "namespace": "ns", "tags": [], "provenance": "user",
           "confidence": 1.0, "metadata": {"evidence_refs": ["test_abc"]},
           "status": "active"}
    pkt = extract(mem)
    ok, warns = validate(pkt, mem)
    assert ok, warns


def test_validate_evidence_dropped_warns():
    mem = {"memory_id": "m1", "content": "Use SQLite. test_abc supports it.",
           "namespace": "ns", "tags": [], "provenance": "user",
           "confidence": 1.0, "metadata": {}, "status": "active"}
    pkt = extract(mem)
    pkt.evidence_refs = []  # simulate drop
    ok, warns = validate(pkt, {"evidence_refs": ["test_abc"]})
    assert not ok
    assert any("evidence" in w for w in warns)


def test_estimate_reduction_explicit():
    pkt = _full_packet()
    est = estimate_reduction("Use SQLite for storage. " * 20, pkt)
    assert est["source_chars"] > 0
    assert est["compressed_chars"] > 0
    assert 0.0 <= est["reduction_ratio"] <= 1.0


# ----- trust compute branches -----
def test_compute_trust_contradiction_penalty():
    s, notes = compute_trust(
        TrustState.USER_FACT, contradiction=True)
    assert s < base_weight(TrustState.USER_FACT)
    assert any("contradiction" in n for n in notes)


def test_compute_trust_superseded_penalty():
    s, notes = compute_trust(TrustState.USER_FACT, superseded=True)
    assert s < 0.1 + 0.05
    assert any("superseded" in n for n in notes)


def test_compute_trust_verified_note():
    s, notes = compute_trust(TrustState.INFERENCE, confidence=0.9, verified=True)
    assert any("explicit transition required" in n for n in notes)


def test_compute_trust_derivation_penalty():
    s1, _ = compute_trust(TrustState.USER_FACT, derivation_depth=0)
    s2, notes = compute_trust(TrustState.USER_FACT, derivation_depth=3)
    assert s2 < s1
    assert any("derivation" in n for n in notes)


def test_compute_trust_ctp_bonus():
    s1, _ = compute_trust(TrustState.TOOL_RESULT, has_ctp_receipt=False)
    s2, notes = compute_trust(TrustState.TOOL_RESULT, has_ctp_receipt=True)
    assert s2 > s1
    assert any("ctp" in n for n in notes)


def test_compute_trust_age_penalty():
    s1, _ = compute_trust(TrustState.USER_FACT, age_days=10)
    s2, notes = compute_trust(TrustState.USER_FACT, age_days=400)
    assert s2 < s1
    assert any("stale" in n for n in notes)
