"""Issue #168: physical HTTP accounting and lost-run reconciliation regression tests."""
from __future__ import annotations
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from capt_runtime.driver_run import DriverRunAggregate
from capt_runtime.drivers.provider import ProviderDriver, ProviderDriverFailure
from capt_runtime.resource_governor import BudgetCeilingExceeded, TokenCostGovernor


class _Response:
    def __init__(self, payload):
        self.payload = payload
    def read(self):
        return json.dumps(self.payload).encode()
    def close(self):
        pass


def _driver(tmp_path, governor):
    d = ProviderDriver(
        str(tmp_path), provider_id="openrouter", model="test/model",
        base_url="https://example.invalid/v1", governor=governor,
    )
    d.runs["run"] = {"state": "running", "dispatchBoundary": "prepared"}
    d._request_deadlines["run"] = time.monotonic() + 10
    return d


def test_three_physical_http_turns_respect_two_request_cap(tmp_path, monkeypatch):
    got = []
    def fake_urlopen(*args, **kwargs):
        got.append(1)
        return _Response({"choices": [{"message": {"content": "ok"}}],
                          "usage": {"prompt_tokens": 4, "completion_tokens": 2, "cost": 0.02}})
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    governor = TokenCostGovernor(max_requests_per_session=2)
    driver = _driver(tmp_path, governor)
    for _ in range(2):
        data = driver._post_json("run", driver.base_url + "/chat/completions",
                                 {"messages": [{"role": "user", "content": "hello"}]}, {})
        assert data["choices"][0]["message"]["content"] == "ok"
    assert len(got) == 2
    assert governor.snapshot()["consumedRequests"] == 2
    assert governor.snapshot()["consumedTokens"] == 12
    assert governor.snapshot()["consumedCostUsd"] == pytest.approx(0.04)
    with pytest.raises(ProviderDriverFailure, match="physical provider request budget exceeded"):
        driver._post_json("run", driver.base_url + "/chat/completions", {}, {})
    assert len(got) == 2


def test_incomplete_request_reserves_slot_without_invented_cost(tmp_path, monkeypatch):
    got = []
    def no_response(*args, **kwargs):
        got.append(1)
        raise TimeoutError("remote timed out")
    monkeypatch.setattr("urllib.request.urlopen", no_response)
    governor = TokenCostGovernor(max_requests_per_session=1)
    driver = _driver(tmp_path, governor)
    with pytest.raises(Exception):
        driver._post_json("run", driver.base_url + "/chat/completions", {}, {})
    assert len(got) == 1
    assert governor.snapshot()["consumedRequests"] == 1
    assert governor.snapshot()["consumedCostUsd"] == 0
    with pytest.raises(ProviderDriverFailure, match="physical provider request budget exceeded"):
        driver._post_json("run", driver.base_url + "/chat/completions", {}, {})
    assert len(got) == 1


def test_response_missing_cost_is_flagged_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k:
                         _Response({"choices":[{"message":{"content":"ok"}}],
                                    "usage":{"prompt_tokens":4,"completion_tokens":2}}))
    governor = TokenCostGovernor()
    driver = _driver(tmp_path, governor)
    driver._post_json("run", driver.base_url + "/chat/completions", {}, {})
    assert governor.snapshot()["consumedRequests"] == 1
    assert governor.snapshot()["providerCostUnknownResponses"] == 1


def test_concurrent_physical_reservations_are_atomic():
    governor = TokenCostGovernor(max_requests_per_session=4)
    def reserve(_):
        try:
            governor.reserve_provider_request(1)
            return True
        except BudgetCeilingExceeded:
            return False
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(reserve, range(40)))
    assert sum(results) == 4
    assert governor.snapshot()["consumedRequests"] == 4


def test_durable_request_boundary_counts_each_new_request_once():
    state = DriverRunAggregate.create({
        "driverRunId":"d", "driverId":"provider",
        "missionId":"m", "taskId":"t",
    })
    for i in range(DriverRunAggregate.MAX_PROVIDER_HTTP_REQUESTS_PER_RUN):
        state = DriverRunAggregate.record_dispatch_boundary(state, "request_started", "2026-10-08T00:00:00Z")
        before = state["providerHttpRequestAttempts"]
        state = DriverRunAggregate.record_dispatch_boundary(state, "request_started", "2026-10-08T00:00:00Z")
        assert state["providerHttpRequestAttempts"] == before
        state = DriverRunAggregate.record_dispatch_boundary(state, "response_started", "2026-10-08T00:00:00Z")
        state = DriverRunAggregate.record_dispatch_boundary(state, "response_completed", "2026-10-08T00:00:00Z")
    assert state["providerHttpRequestAttempts"] == DriverRunAggregate.MAX_PROVIDER_HTTP_REQUESTS_PER_RUN
    with pytest.raises(Exception, match="PROVIDER_HTTP_REQUEST_ATTEMPT_CAP_EXCEEDED"):
        DriverRunAggregate.record_dispatch_boundary(state, "request_started", "2026-10-08T00:00:00Z")


def test_lost_run_reconciliation_from_historical_event_boundaries():
    from capt_runtime.reconciliation import reconcile_provider_http_attempts
    def ev(boundary):
        return {"eventType":"DriverRunDispatchBoundaryRecorded",
                "payload":{"driverRunId":"dr-lost","dispatchBoundary":boundary}}
    events = [ev("request_started"), ev("response_started"), ev("response_completed"),
              ev("request_started"), ev("response_started"), ev("response_completed"),
              ev("request_started")]
    result = reconcile_provider_http_attempts(
        {"driverRunId":"dr-lost","state":"lost","dispatchBoundary":"request_started"},
        events)
    assert result["attemptsReservedByEvent"] == 3
    assert result["responsesCompleted"] == 2
    assert result["requestsWithoutCompletedResponses"] == 1
    assert result["billingOfUnresolvedCalls"] == "unknown"
    assert result["disposition"] == "retry_forbidden"
    assert result["automaticReplayPermitted"] is False


def test_reconciliation_does_not_promote_unverified_artifact():
    from capt_runtime.reconciliation import reconcile_provider_http_attempts
    events = [
        {"eventType":"DriverRunDispatchBoundaryRecorded",
         "payload":{"driverRunId":"dr-lost","dispatchBoundary":x}}
        for x in ["request_started","response_started","response_completed","result_persisted"]
    ]
    run = {"driverRunId":"dr-lost","state":"lost","dispatchBoundary":"result_persisted"}
    result = reconcile_provider_http_attempts(run, events, artifact_verified=False)
    assert result["disposition"] == "retry_forbidden"
    verified = reconcile_provider_http_attempts(run, events, artifact_verified=True)
    assert verified["disposition"] == "reconciled_completed"
    assert verified["automaticReplayPermitted"] is False


def test_reconciliation_rejects_cross_run_event_contamination():
    from capt_runtime.reconciliation import reconcile_provider_http_attempts, ReconciliationError
    with pytest.raises(ReconciliationError, match="RUN_MISMATCH"):
        reconcile_provider_http_attempts(
            {"driverRunId":"dr-a","state":"lost","dispatchBoundary":"request_started"},
            [{"eventType":"DriverRunDispatchBoundaryRecorded",
              "payload":{"driverRunId":"dr-b","dispatchBoundary":"request_started"}}])
