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
