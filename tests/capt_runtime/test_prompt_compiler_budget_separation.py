"""Session aggregate budget must not masquerade as per-stage model context."""
from __future__ import annotations

import pytest

from capt_runtime.prompt_compiler import (
    BoundedPromptCompilerRunner, CompilerProvider, PromptCompileRequest, PromptStageName
)
from capt_runtime.resource_governor import TokenCostGovernor, BudgetCeilingExceeded
from desktop.prompt_compiler_provider import (
    PromptCompilerSelection, _compiler_from_selection,
    _COMPILER_SESSION_TOKEN_CAP,
    _COMPILER_MAX_ESTIMATED_INPUT_TOKENS,
)


def _structured(payload):
    return {
        "stage": payload["stage"], "outcome": "report", "scope": "bounded",
        "inputs": [], "outputs": ["report"], "constraints": [],
        "successCriteria": ["clear"], "ambiguities": [],
        "requestedCapabilities": [],
    }


def test_sequential_compiler_stages_can_exceed_legacy_session_ceiling():
    calls = []
    governor = TokenCostGovernor(max_tokens_per_session=_COMPILER_SESSION_TOKEN_CAP)
    runner = BoundedPromptCompilerRunner(
        lambda payload: (calls.append(payload["stage"]), _structured(payload))[1],
        governor=governor, max_estimated_prompt_tokens_per_request=98_304,
    )
    # Each stage below uses ~40K estimated input tokens. The combined four
    # stages consume >131072, which is valid for an aggregate 1M session budget.
    req = PromptCompileRequest(original_prompt="A" * 65_000)
    provider = CompilerProvider("local", "fixture", "local")
    for stage in (PromptStageName.OMNI, PromptStageName.META,
                  PromptStageName.FORGE, PromptStageName.SIGMA):
        runner.run(stage, req, provider,
                   stage_context={"boundedFixtureEvidence": "B" * 25_000})
    assert len(calls) == 4
    assert governor.consumed_tokens > 155_153
    assert governor.consumed_tokens < _COMPILER_SESSION_TOKEN_CAP


def test_individual_stage_still_fails_before_transport_if_context_exceeded():
    calls = []
    governor = TokenCostGovernor(max_tokens_per_session=1_000_000)
    runner = BoundedPromptCompilerRunner(
        lambda payload: calls.append(payload), governor=governor,
        max_estimated_prompt_tokens_per_request=4_000,
    )
    with pytest.raises(ValueError, match="COMPILER_STAGE_CONTEXT_LIMIT"):
        runner.run(PromptStageName.OMNI,
                   PromptCompileRequest(original_prompt="x" * 18_000),
                   CompilerProvider("local", "fixture", "local"))
    assert calls == []
    assert governor.consumed_requests == 0
    assert governor.consumed_tokens == 0


def test_stage_guard_rejects_invalid_values():
    for invalid in (-1, 0, True, "100"):
        with pytest.raises(ValueError, match="COMPILER_PROMPT_TOKEN_BOUND_INVALID"):
            BoundedPromptCompilerRunner(_structured,
                                        max_estimated_prompt_tokens_per_request=invalid)


def test_existing_session_cost_request_and_token_caps_remain_enforced():
    gov = TokenCostGovernor(max_tokens_per_session=30_000,
                            max_cost_usd_per_session=0.01,
                            max_requests_per_session=2)
    runner = BoundedPromptCompilerRunner(_structured, governor=gov)
    req = PromptCompileRequest(original_prompt="x" * 8_000)
    provider = CompilerProvider("local", "fixture", "local")
    runner.run(PromptStageName.OMNI, req, provider)
    runner.run(PromptStageName.META, req, provider)
    with pytest.raises(BudgetCeilingExceeded, match="REQUEST_CEILING_BREACHED"):
        runner.run(PromptStageName.FORGE, req, provider)
    assert gov.consumed_requests == 2


def test_core_transport_builder_uses_separate_limits(monkeypatch):
    # No model call or secret retrieval: inspect only compiler wiring.
    sel = PromptCompilerSelection(
        "mtplx", "fixture", "http://127.0.0.1:19000/v1", "local"
    )
    compiler = _compiler_from_selection(sel)
    governor = compiler._runner._governor
    assert governor.max_tokens_per_session == 1_000_000
    assert governor.max_cost_usd_per_session == 0.01
    assert governor.max_requests_per_session == 32
    assert compiler._runner._max_prompt_tokens == _COMPILER_MAX_ESTIMATED_INPUT_TOKENS
    assert _COMPILER_MAX_ESTIMATED_INPUT_TOKENS + 32_768 == 131_072
