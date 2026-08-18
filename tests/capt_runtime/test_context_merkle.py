"""CAPT-UPG-013 component-provenance and stable-prefix tests."""

from copy import deepcopy

from capt_runtime.context_merkle import (
    build_context_merkle,
    build_prompt_prefix_plan,
    diff_context_merkle,
)


def _pack():
    return {
        "contextPackDigest": "sha256:" + "a" * 64,
        "policyVersion": 3,
        "triggerBoundary": 64000,
        "contextUsageBefore": 12000,
        "contextUsageAfter": 12000,
        "selectedRecords": [
            {
                "recordId": "mem-1",
                "digest": "sha256:" + "1" * 64,
                "retrievalScore": 0.9,
                "retrievalReason": "selected by CAPT memory policy",
            }
        ],
        "excludedRecords": [],
        "compressionActions": [],
        "summariesGenerated": [],
        "provenanceRetained": True,
        "unresolvedConflicts": [],
        "staleRecords": [],
        "redactions": [],
        "tokenBudget": 32000,
        "previousContextPackDigest": None,
        "missionId": "m-1",
        "taskId": "t-1",
        "driverRunId": "dr-1",
    }


def test_component_merkle_localizes_selected_record_change():
    before_pack = _pack()
    after_pack = deepcopy(before_pack)
    after_pack["selectedRecords"][0]["digest"] = "sha256:" + "2" * 64
    after_pack["contextPackDigest"] = "sha256:" + "b" * 64

    before = build_context_merkle(before_pack)
    after = build_context_merkle(after_pack)
    delta = diff_context_merkle(before, after)

    assert delta["rootChanged"] is True
    assert delta["changedComponents"] == ["selection"]
    assert set(delta["unchangedComponents"]) == {
        "policy", "usage", "exclusions", "compression", "lineage"
    }
    assert before["semantics"]["replacesContextPackDigest"] is False
    assert before["semantics"]["providerCacheHitClaim"] is False


def test_component_merkle_is_deterministic_for_equivalent_pack():
    one = build_context_merkle(_pack())
    two = build_context_merkle(deepcopy(_pack()))
    assert one["rootDigest"] == two["rootDigest"]
    assert one["leaves"] == two["leaves"]


def test_prompt_prefix_plan_separates_prefix_stability_from_full_prompt_change():
    sections = [
        {"identity": "system", "text": "stable system contract"},
        {"identity": "policy", "text": "stable policy"},
        {"identity": "task", "text": "task A"},
    ]
    changed_after = deepcopy(sections)
    changed_after[2]["text"] = "task B"

    first = build_prompt_prefix_plan(sections, breakpoint_after="policy")
    second = build_prompt_prefix_plan(changed_after, breakpoint_after="policy")

    assert first["prefixDigest"] == second["prefixDigest"]
    assert first["fullPromptDigest"] != second["fullPromptDigest"]
    assert first["providerCacheHitClaim"] is False
    assert first["exactPrefixRequired"] is True

    changed_before = deepcopy(sections)
    changed_before[1]["text"] = "changed policy"
    third = build_prompt_prefix_plan(changed_before, breakpoint_after="policy")
    assert third["prefixDigest"] != first["prefixDigest"]
