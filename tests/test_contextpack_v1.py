import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from capt_solo.contextpack import (  # noqa: E402
    Assumption, Mission, MissionIntent, RecordRef, TokenBudget, build_context_pack,
    canonical_json, render_handoff, validate_context_pack,
)
from capt_solo.memory.models import AntiTokenPacket, ContextBuildResult, ContextItem  # noqa: E402


CLOCK = "2026-07-28T00:00:00Z"


def _intent():
    return MissionIntent("fix safely", "high", ("truth over speed",), "tests pass", ("local only",))


def _budget(estimated=5, available=10):
    return TokenBudget(10, 0, available, estimated, available-estimated, "chars/4", "chars_div_4", "heuristic_estimated")


def _ref(identifier="e1", text="tests/test_a.py failed with error 7; do not delete v1.2.3"):
    return RecordRef(identifier, "sha256:x", "test", {"content": text})


def _pack(rendered="Never delete evidence. tests/test_a.py failed with error 7; do not delete v1.2.3", **kwargs):
    values = dict(invariants=(_ref("i1", "Never delete evidence"),), evidence=(_ref(),), memory=(), receipts=(), rendered_context=rendered, token_budget=_budget(), evaluation_clock=CLOCK, confidence=0.8, assumption_review_status="reviewed_none_found", protected_fact_review_status="reviewed")
    values.update(kwargs)
    return build_context_pack(Mission("m1", "repair", ("tests pass",)), _intent(), values.pop("assumptions", ()), **values)


def test_deterministic_pack_digest_and_deep_immutability():
    first, second = _pack(), _pack()
    assert first.digest == second.digest
    assert canonical_json(first.to_dict()) == canonical_json(second.to_dict())
    with pytest.raises((AttributeError, TypeError)):
        first.evidence += (_ref("x"),)


def test_source_facts_not_rendered_facts_block_fidelity():
    pack = _pack(rendered="summary omitted all source details")
    result = validate_context_pack(pack)
    assert result.status == "BLOCK"
    assert result.blocks[0].category == "FIDELITY_BLOCK"
    assert result.missing_facts


def test_empty_assumptions_are_valid_after_explicit_review():
    assert validate_context_pack(_pack()).status == "PASS"
    assert validate_context_pack(_pack(assumption_review_status="not_reviewed")).status == "BLOCK"


def test_budget_block_and_external_validation_do_not_mutate_pack():
    pack = _pack(token_budget=_budget(estimated=11, available=10))
    before = pack.digest
    result = validate_context_pack(pack)
    assert result.status == "BLOCK"
    assert any(block.category == "BUDGET_BLOCK" for block in result.blocks)
    assert pack.digest == before


def test_handoff_is_derived_and_links_final_digest():
    pack = _pack()
    handoff = render_handoff(pack)
    assert handoff.pack_digest == pack.digest
    assert pack.handoff.pack_digest == ""


def test_clock_normalization_and_invalid_confidence_rejected():
    assert _pack(evaluation_clock="2026-07-27T19:00:00-05:00").evaluation_clock == CLOCK
    with pytest.raises(ValueError): _pack(confidence=1.1)


def test_canonical_round_trip_and_unknown_field_policy():
    pack = _pack()
    restored = type(pack).from_dict(pack.to_dict())
    assert canonical_json(restored.to_dict()) == canonical_json(pack.to_dict())
    future = pack.to_dict(); future["future_semantic"] = {"x": 1}
    with pytest.raises(ValueError): type(pack).from_dict(future)
    inspected, unknown = type(pack).from_dict(future, compatibility_inspection=True)
    assert inspected.digest == pack.digest
    assert unknown


def test_existing_context_builder_result_adapter_ignores_trace_id():
    pkt = AntiTokenPacket("m1", "fact", "Never delete evidence v1.2.3")
    result = ContextBuildResult("q", [ContextItem("m1", 1.0, True, "selected", pkt)],
                                "Never delete evidence v1.2.3", [], [], [], 1, 1, 0.0,
                                "random-trace", {})
    pack = __import__("capt_solo.contextpack", fromlist=["build_from_context_result"]).build_from_context_result(
        Mission("m", "o"), _intent(), result, invariants=(), evidence=(), receipts=(),
        token_budget=_budget(), evaluation_clock=CLOCK, confidence=1.0,
        assumption_review_status="reviewed_none_found", protected_fact_review_status="reviewed")
    assert pack.memory[0].record_digest.startswith("sha256:")
