"""Tests for AI resource and financial ceiling governor (CAPT-UPG-004)."""

import pytest
from capt_runtime.resource_governor import TokenCostGovernor, BudgetCeilingExceeded
from capt_runtime.drivers.provider import ProviderDriver, ProviderDriverFailure


def test_token_cost_governor_trips_on_request_cap():
    gov = TokenCostGovernor(max_requests_per_session=2)
    gov.check_pre_dispatch()
    gov.record_usage(prompt_tokens=10, completion_tokens=10)

    gov.check_pre_dispatch()
    gov.record_usage(prompt_tokens=10, completion_tokens=10)

    # 3rd request should breach ceiling
    with pytest.raises(BudgetCeilingExceeded, match="REQUEST_CEILING_BREACHED"):
        gov.check_pre_dispatch()


def test_token_cost_governor_trips_on_token_cap():
    gov = TokenCostGovernor(max_tokens_per_session=100)
    gov.check_pre_dispatch(estimated_prompt_tokens=50)
    gov.record_usage(prompt_tokens=50, completion_tokens=40)

    # Consumed 90 tokens; next request estimating 20 tokens will breach (90 + 20 > 100)
    with pytest.raises(BudgetCeilingExceeded, match="TOKEN_CEILING_BREACHED"):
        gov.check_pre_dispatch(estimated_prompt_tokens=20)


def test_token_cost_governor_trips_on_cost_cap():
    gov = TokenCostGovernor(max_cost_usd_per_session=1.0)
    gov.check_pre_dispatch()
    gov.record_usage(prompt_tokens=10, completion_tokens=10, cost_usd=1.05)

    with pytest.raises(BudgetCeilingExceeded, match="COST_CEILING_BREACHED"):
        gov.check_pre_dispatch()
