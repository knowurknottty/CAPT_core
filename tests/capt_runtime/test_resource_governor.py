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


def test_provider_driver_budget_rejection_occurs_before_network_dispatch(tmp_path, monkeypatch):
    calls = []

    def forbidden_urlopen(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("network dispatch must not occur after budget rejection")

    monkeypatch.setattr("urllib.request.urlopen", forbidden_urlopen)
    gov = TokenCostGovernor(max_requests_per_session=0)
    driver = ProviderDriver(
        str(tmp_path), provider_id="openrouter", model="test/model",
        base_url="https://example.invalid/v1", governor=gov,
    )
    import asyncio
    with pytest.raises(ProviderDriverFailure, match="REQUEST_CEILING_BREACHED"):
        asyncio.run(driver.submit({
            "driverRunId": "dr-budget", "missionId": "m-budget",
            "taskId": "t-budget", "contextSlice": {},
            "submittedAt": "2026-08-19T00:00:00Z",
        }))
    assert calls == []


def test_shared_governor_survives_fresh_provider_driver_instances(tmp_path, monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b'{"choices":[{"message":{"content":"ok"}}],"usage":{"prompt_tokens":2,"completion_tokens":1}}'

    calls = []

    def fake_urlopen(*args, **kwargs):
        calls.append((args, kwargs))
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    gov = TokenCostGovernor(max_requests_per_session=1)
    import asyncio
    first = ProviderDriver(
        str(tmp_path / "one"), provider_id="openrouter", model="test/model",
        base_url="https://example.invalid/v1", governor=gov,
    )
    asyncio.run(first.submit({
        "driverRunId": "dr-one", "missionId": "m", "taskId": "t",
        "contextSlice": {}, "submittedAt": "2026-08-19T00:00:00Z",
    }))
    second = ProviderDriver(
        str(tmp_path / "two"), provider_id="openrouter", model="test/model",
        base_url="https://example.invalid/v1", governor=gov,
    )
    with pytest.raises(ProviderDriverFailure, match="REQUEST_CEILING_BREACHED"):
        asyncio.run(second.submit({
            "driverRunId": "dr-two", "missionId": "m", "taskId": "t2",
            "contextSlice": {}, "submittedAt": "2026-08-19T00:00:00Z",
        }))
    assert len(calls) == 1


def test_cost_alert_fires_once_before_hard_cap_without_sensitive_payload():
    alerts = []
    gov = TokenCostGovernor(
        max_cost_usd_per_session=10.0,
        alert_cost_usd=7.5,
        on_cost_alert=alerts.append,
    )
    first = gov.record_usage(prompt_tokens=10, completion_tokens=10, cost_usd=7.0)
    assert first["costAlert"] is None
    assert alerts == []

    second = gov.record_usage(prompt_tokens=10, completion_tokens=10, cost_usd=0.75)
    assert second["costAlert"]["kind"] == "spend_threshold_crossed"
    assert second["costAlert"]["thresholdUsd"] == 7.5
    assert second["costAlert"]["maxCostUsd"] == 10.0
    assert len(alerts) == 1
    assert alerts[0] == second["costAlert"]
    assert set(alerts[0]) == {
        "kind", "thresholdUsd", "consumedCostUsd", "maxCostUsd", "consumedRequests"
    }

    third = gov.record_usage(prompt_tokens=10, completion_tokens=10, cost_usd=0.25)
    assert third["costAlert"] is None
    assert len(alerts) == 1
    gov.check_pre_dispatch()


def test_cost_alert_configuration_must_be_below_hard_cap():
    with pytest.raises(ValueError, match="COST_ALERT_THRESHOLD_INVALID"):
        TokenCostGovernor(max_cost_usd_per_session=5.0, alert_cost_usd=5.0)
