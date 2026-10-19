"""Strict council request-count and output feasibility gates, no real network."""
from __future__ import annotations

import asyncio
import json

import pytest

from capt_runtime.cohort_contract import normalize_cohort_spec, compile_cohort_objective
from capt_runtime.drivers.provider import ProviderDriver, ProviderDriverFailure
from capt_runtime.resource_governor import TokenCostGovernor


def spec(*, requests=None, vessels=22):
    raw = {
        "cohortId": "strict-one-physical-inference",
        "configurationId": "frozen-demo",
        "vesselsPerCohort": vessels,
        "vesselCharterPolicy": {"schemaVersion": "2.0.0"},
    }
    if requests is not None:
        raw["maxPhysicalProviderRequests"] = requests
    return normalize_cohort_spec(raw)


def work_order(rid):
    return {
        "driverRunId": rid, "missionId": "m-strict", "taskId": "t-strict",
        "contextSlice": {}, "submittedAt": "2026-10-18T00:00:00Z",
    }


class FakeResponse:
    def read(self):
        return json.dumps({
            "choices": [{"message": {"content": "Untrusted model observation"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 17},
        }).encode()

    def close(self):
        pass


def test_strict_cohort_defaults_to_one_bound_physical_request():
    s=spec()
    assert s["maxPhysicalProviderRequests"] == 1
    assert normalize_cohort_spec(s) == s
    body = compile_cohort_objective(
        "Inspect only the given corpus", provider="openrouter",
        model="test/model", cohort_spec=s,
    )
    assert "approved_max_physical_provider_requests: 1" in body
    assert "logical_vessels: 22" in body


@pytest.mark.parametrize("bad", [0, -1, 25, True, 1.5, "2"])
def test_physical_request_bound_refuses_invalid_values(bad):
    with pytest.raises(ValueError, match="COHORT_PHYSICAL_PROVIDER_REQUEST_LIMIT_INVALID"):
        spec(requests=bad)


def test_explicit_bounded_multi_request_is_preserved_by_approval_normalizer():
    s=spec(requests=3)
    assert s["maxPhysicalProviderRequests"] == 3
    assert normalize_cohort_spec(s) == s


def test_strict_one_call_does_not_advertise_a_tool_loop(monkeypatch,tmp_path):
    seen=[]
    def fake_urlopen(request,**kwargs):
        seen.append(json.loads(request.data))
        return FakeResponse()
    monkeypatch.setattr("capt_runtime.http_client.open_url", fake_urlopen)

    class ReadOnlyToolBridge:
        def openai_tools(self):
            raise AssertionError("strict one-call model must not expose multi-round tools")

    driver=ProviderDriver(
        str(tmp_path), provider_id="openrouter", model="test/model",
        base_url="https://example.invalid/v1", cohort_spec=spec(),
        tool_bridge=ReadOnlyToolBridge(),
    )
    receipt=asyncio.run(driver.submit(work_order("dr-single-strict")))
    assert receipt["state"] == "completed"
    assert len(seen) == 1
    assert "tools" not in seen[0]
    assert receipt["diagnostics"]["resourceUsage"]["consumedRequests"] == 1
    assert driver.runs["dr-single-strict"]["physicalRequestSlotsConsumed"] == 1


def test_bound_physical_request_cap_blocks_third_network_attempt(monkeypatch,tmp_path):
    sent=[]
    def fake_urlopen(request,**kwargs):
        sent.append(json.loads(request.data))
        return FakeResponse()
    monkeypatch.setattr("capt_runtime.http_client.open_url", fake_urlopen)
    driver=ProviderDriver(
        str(tmp_path), provider_id="openrouter", model="test/model",
        base_url="https://example.invalid/v1", cohort_spec=spec(requests=2),
    )
    rid="dr-limited-two"
    driver.runs[rid]={"state":"running"}
    kwargs=(rid,"https://example.invalid/v1/chat/completions",{"model":"test/model","messages":[]},{})
    driver._post_json(*kwargs)
    driver._post_json(*kwargs)
    with pytest.raises(ProviderDriverFailure,match="physical provider request ceiling exhausted") as exc:
        driver._post_json(*kwargs)
    assert exc.value.diagnostic_code == "PROVIDER_BUDGET_EXCEEDED"
    assert len(sent) == 2
    assert driver.runs[rid]["physicalRequestSlotsConsumed"] == 2


def test_impossible_charter_output_budget_fails_before_network(monkeypatch,tmp_path):
    def forbidden(*args,**kwargs):
        raise AssertionError("no network request should be dispatched")
    monkeypatch.setattr("capt_runtime.http_client.open_url", forbidden)
    driver=ProviderDriver(
        str(tmp_path), provider_id="openrouter", model="test/model",
        base_url="https://example.invalid/v1", cohort_spec=spec(vessels=22),
        governor=TokenCostGovernor(max_output_tokens_per_request=512),
    )
    rid="dr-unfittable-charter"
    with pytest.raises(ProviderDriverFailure, match="cannot fit") as exc:
        asyncio.run(driver.submit(work_order(rid)))
    assert exc.value.diagnostic_code == "PROVIDER_BUDGET_EXCEEDED"
    assert driver.runs[rid]["dispatchBoundary"] == "budget_rejected"
    assert driver.governor.snapshot()["consumedRequests"] == 0

def test_tool_execution_failure_is_typed_and_never_leaks_exception(monkeypatch,tmp_path):
    """No raw exception or tool args reach the typed provider error."""
    class ToolBridge:
        max_calls=2
        def openai_tools(self):
            return [{"type":"function","function":{"name":"capt_file_read"}}]
        def execute_call(self,*a,**kw):
            raise RuntimeError("secret-tainted-tool-error must not leak")

    class ToolResponse:
        def read(self):
            return json.dumps({
                "choices":[{"message":{"role":"assistant","tool_calls":[{
                    "id":"call-1","type":"function",
                    "function":{"name":"capt_file_read","arguments":"{}"},
                }]}}],
                "usage":{"prompt_tokens":25,"completion_tokens":9},
            }).encode()
        def close(self):
            pass
    monkeypatch.setattr("capt_runtime.http_client.open_url", lambda *_a,**_kw:ToolResponse())
    driver=ProviderDriver(
        str(tmp_path),provider_id="openrouter",model="fixture",
        base_url="https://example.invalid/v1",cohort_spec=spec(requests=2),
        tool_bridge=ToolBridge(),
    )
    with pytest.raises(ProviderDriverFailure) as caught:
        asyncio.run(driver.submit(work_order("dr-tool-failure")))
    assert caught.value.diagnostic_code=="PROVIDER_TOOL_FAILURE"
    assert caught.value.diagnostic_phase=="tool_execution"
    assert "secret-tainted" not in str(caught.value)
    assert driver.governor.snapshot()["consumedRequests"]==1
