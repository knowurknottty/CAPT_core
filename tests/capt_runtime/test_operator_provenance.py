import pytest

from capt_runtime.operator_provenance import (
    build_cognitive_provenance, build_prompt_assembly, effective_context_budget,
)


def test_assembly_is_ordered_and_model_visible_prompt_is_digest_bound():
    assembly = build_prompt_assembly(
        human_prompt="Inspect the repository and report evidence.", response_mode="MIN",
        enhancement_engine="FORGE", context_pack_digest="sha256:" + "a" * 64,
        tool_schema_digest="sha256:" + "b" * 64,
    )
    assert [s["identity"] for s in assembly["sections"]] == [
        "capt-governance", "response-mode", "human-task", "context-reference", "tool-surface"]
    assert "PASS/FAIL" in assembly["modelVisiblePrompt"]
    assert assembly["modelVisiblePromptDigest"].startswith("sha256:")


def test_provenance_has_requested_effective_truth_and_no_credential_material():
    assembly = build_prompt_assembly(
        human_prompt="test task", response_mode="SPOCK", enhancement_engine="OFF",
        context_pack_digest="sha256:" + "a" * 64, tool_schema_digest="sha256:" + "b" * 64)
    env = build_cognitive_provenance(
        assembly=assembly, provider_id="ollama", model="local-model",
        requested_context_budget=256_000, effective_context_budget_value=8192,
        human_verification_required=False, correlation={"driverRunId": "dr-1"})
    assert env["requestedContextBudget"] == 256_000
    assert env["effectiveContextBudget"] == 8192
    assert env["credentialMaterial"] == "not_recorded"
    assert "apiKey" not in str(env)


def test_effective_context_budget_rejects_unsupported_selector_value():
    assert effective_context_budget(32_000, 8_192) == 8_192
    with pytest.raises(ValueError, match="REQUESTED_CONTEXT_BUDGET_INVALID"):
        effective_context_budget(1, 8_192)
