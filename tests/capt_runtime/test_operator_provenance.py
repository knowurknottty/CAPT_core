import pytest

from capt_runtime.operator_provenance import (
    build_cognitive_provenance,
    build_prompt_assembly,
    effective_context_budget,
    validate_model_visible_prompt_budget,
)


def test_assembly_is_ordered_and_model_visible_prompt_is_digest_bound():
    assembly = build_prompt_assembly(
        human_prompt="Inspect the repository and report evidence.",
        response_mode="MIN",
        enhancement_engine="FORGE",
        context_pack_digest="sha256:" + "a" * 64,
        tool_schema_digest="sha256:" + "b" * 64,
    )
    assert [section["identity"] for section in assembly["sections"]] == [
        "capt-governance",
        "response-mode",
        "human-task",
        "context-reference",
        "tool-surface",
    ]
    assert "PASS/FAIL" in assembly["modelVisiblePrompt"]
    assert assembly["modelVisiblePromptDigest"].startswith("sha256:")


def test_provenance_has_requested_effective_truth_and_no_credential_material():
    assembly = build_prompt_assembly(
        human_prompt="test task",
        response_mode="SPOCK",
        enhancement_engine="OFF",
        context_pack_digest="sha256:" + "a" * 64,
        tool_schema_digest="sha256:" + "b" * 64,
    )
    env = build_cognitive_provenance(
        assembly=assembly,
        provider_id="ollama",
        model="local-model",
        requested_context_budget=256_000,
        effective_context_budget_value=8192,
        human_verification_required=False,
        correlation={"driverRunId": "dr-1"},
    )
    assert env["requestedContextBudget"] == 256_000
    assert env["effectiveContextBudget"] == 8192
    assert env["effectiveContextBudgetStatus"] == "known"
    assert env["credentialMaterial"] == "not_recorded"
    assert env["reconstructionScope"] == "prompt_and_references"
    assert "apiKey" not in str(env)


def test_unknown_provider_capacity_remains_unknown():
    assert effective_context_budget(256_000, 0) is None
    assembly = build_prompt_assembly(
        human_prompt="test task",
        response_mode="SPOCK",
        enhancement_engine="OFF",
        context_pack_digest="sha256:" + "a" * 64,
        tool_schema_digest="sha256:" + "b" * 64,
    )
    env = build_cognitive_provenance(
        assembly=assembly,
        provider_id="openrouter",
        model="m",
        requested_context_budget=256_000,
        effective_context_budget_value=None,
        human_verification_required=True,
        correlation={},
    )
    assert env["effectiveContextBudget"] is None
    assert env["effectiveContextBudgetStatus"] == "unknown"


def test_effective_context_budget_rejects_unsupported_selector_value():
    assert effective_context_budget(32_000, 8_192) == 8_192
    with pytest.raises(ValueError, match="REQUESTED_CONTEXT_BUDGET_INVALID"):
        effective_context_budget(1, 8_192)


def test_prompt_assembly_rejects_noncanonical_engine():
    with pytest.raises(ValueError, match="ENHANCEMENT_ENGINE_INVALID"):
        build_prompt_assembly(
            human_prompt="test task",
            response_mode="SPOCK",
            enhancement_engine="FORGE_REAL_PROVEN_FINAL",
            context_pack_digest="sha256:" + "a" * 64,
            tool_schema_digest="sha256:" + "b" * 64,
        )


def test_model_visible_prompt_budget_uses_token_capacity_not_4096_character_ceiling():
    evidence = validate_model_visible_prompt_budget(
        "x" * 20_000,
        requested_context_budget=32_000,
        effective_context_budget_value=32_000,
    )
    assert evidence["estimatedPromptTokens"] == 5_000
    assert evidence["capacityTokens"] == 32_000
    assert evidence["outputReserveTokens"] == 4_096
    assert evidence["promptTokenLimit"] == 27_904


def test_model_visible_prompt_budget_rejects_prompt_that_consumes_output_reserve():
    with pytest.raises(ValueError, match="MODEL_VISIBLE_PROMPT_TOO_LONG"):
        validate_model_visible_prompt_budget(
            "x" * 120_000,
            requested_context_budget=32_000,
            effective_context_budget_value=32_000,
        )


def test_model_visible_prompt_budget_uses_requested_budget_when_provider_capacity_unknown():
    evidence = validate_model_visible_prompt_budget(
        "x" * 100_000,
        requested_context_budget=64_000,
        effective_context_budget_value=None,
    )
    assert evidence["capacityTokens"] == 64_000
    assert evidence["promptTokenLimit"] == 59_904
