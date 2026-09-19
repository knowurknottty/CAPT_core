from __future__ import annotations

import pytest

from capt_runtime.errors import AuthorityViolation


def test_safe_defaults_are_local_and_private():
    from capt_runtime.bot_locality import compile_onboarding_locality
    policy = compile_onboarding_locality({})
    assert policy == {"defaultRuntime": "local", "privateData": "local_only"}


def test_public_cloud_work_can_coexist_with_local_private_data():
    from capt_runtime.bot_locality import compile_onboarding_locality, runtime_for_data
    policy = compile_onboarding_locality({"allowCloudExecution": True})
    assert policy == {"defaultRuntime": "either", "privateData": "local_only"}
    assert runtime_for_data(policy, "public") == "either"
    assert runtime_for_data(policy, "project") == "local"
    assert runtime_for_data(policy, "user") == "local"
    assert runtime_for_data(policy, "secret") == "local"


def test_explicit_private_cloud_choice_is_visible_in_compiled_policy():
    from capt_runtime.bot_locality import compile_onboarding_locality, runtime_for_data
    policy = compile_onboarding_locality({
        "allowCloudExecution": True,
        "allowPrivateDataInCloud": True,
        "preferredRuntime": "cloud",
    })
    assert policy == {"defaultRuntime": "cloud", "privateData": "cloud_allowed"}
    assert runtime_for_data(policy, "user") == "cloud"


def test_contradictory_cloud_preferences_fail_closed():
    from capt_runtime.bot_locality import compile_onboarding_locality
    with pytest.raises(AuthorityViolation, match="PRIVATE_CLOUD_REQUIRES_CLOUD_EXECUTION"):
        compile_onboarding_locality({"allowPrivateDataInCloud": True})
    with pytest.raises(AuthorityViolation, match="CLOUD_RUNTIME_NOT_ALLOWED"):
        compile_onboarding_locality({"preferredRuntime": "cloud"})
