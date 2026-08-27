from __future__ import annotations

import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.prompt_compiler import PromptCompilerProviderPolicy


def test_policy_prefers_healthy_verified_local_endpoint():
    resolved = PromptCompilerProviderPolicy().resolve(
        local_available=True,
        remote_allowed=False,
    )

    assert resolved.endpoint_class == "local"


def test_policy_refuses_remote_compilation_without_explicit_authorization():
    with pytest.raises(AuthorityViolation):
        PromptCompilerProviderPolicy().resolve(
            local_available=False,
            remote_allowed=False,
            requested_remote="openrouter",
        )


def test_runner_uses_existing_token_cost_governor_for_compiler_dispatch():
    from capt_runtime.prompt_compiler import BoundedPromptCompilerRunner, CompilerProvider, PromptCompileRequest, PromptStageName
    from capt_runtime.resource_governor import TokenCostGovernor

    governor = TokenCostGovernor(max_requests_per_session=2)

    def transport(payload):
        return {
            "stage": payload["stage"], "outcome": "report",
            "scope": "bounded", "inputs": [], "outputs": ["report"],
            "constraints": [], "successCriteria": ["clear"],
            "ambiguities": [], "requestedCapabilities": [],
        }

    runner = BoundedPromptCompilerRunner(transport, governor=governor)
    runner.run(
        PromptStageName.OMNI,
        PromptCompileRequest(original_prompt="Write a report about the failed test."),
        CompilerProvider("ollama", "local", "local"),
    )

    assert governor.consumed_requests == 1
    assert governor.consumed_tokens > 0


def test_compiler_rejects_remote_provider_without_separate_compilation_consent():
    from capt_runtime.prompt_compiler import (
        BoundedPromptCompilerRunner,
        CompilerProvider,
        PromptCompileRequest,
        PromptCompiler,
    )

    def transport(_payload):
        raise AssertionError("remote transport must not be called")

    request = PromptCompileRequest(
        original_prompt="Write a report about the failed test.",
        execution_provider="openrouter",
        remote_compilation_authorized=False,
    )
    compiler = PromptCompiler(
        runner=BoundedPromptCompilerRunner(transport),
        provider=CompilerProvider("openrouter", "remote-model", "remote"),
    )

    with pytest.raises(AuthorityViolation, match="REMOTE_COMPILATION_NOT_AUTHORIZED"):
        compiler.compile(request)


def test_policy_prefers_explicit_authorized_remote_over_available_local():
    resolved = PromptCompilerProviderPolicy().resolve(
        local_available=True,
        remote_allowed=True,
        requested_remote="openrouter",
        local_provider="mtplx",
        local_model="qwen",
    )
    assert resolved.provider_id == "openrouter"
    assert resolved.endpoint_class == "remote"
