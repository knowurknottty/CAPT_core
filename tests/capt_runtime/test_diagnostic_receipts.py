"""Issue #168: production persistence and zero-network diagnostic tests."""
from __future__ import annotations

import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from capt_runtime.diagnostic_receipts import (
    council_submission_digest,
    safe_cohort_receipt,
    safe_provider_failure,
)
from capt_runtime.drivers.provider import ProviderDriverFailure
from capt_runtime.errors import IdempotencyConflict
from capt_runtime.store import EventStore
from desktop.capt_runtime_service import RuntimeQueryService
from desktop.m1_command_service import RuntimeCommandService
from capt_runtime.cohort_contract import default_charter_policy


def _db(tmp_path):
    return EventStore(str(tmp_path / "capt-ledger.db"))


def test_diagnostics_are_encrypted_and_dont_persist_secret_messages(tmp_path):
    store = _db(tmp_path)
    secret = "sk-proj_super-secret-token_NOT_FOR_LEDGER"
    bad = ProviderDriverFailure(
        "upstream said " + secret, diagnostic_code="PROVIDER_HTTP_ERROR",
        diagnostic_phase="response_headers", http_status=429,
    )
    record = safe_provider_failure(
        bad, driver_run_id="dr-test", model="test/model", provider="openrouter",
        dispatch_boundary="request_started", request_attempts=2,
    )
    assert record["failureCode"] == "PROVIDER_HTTP_ERROR"
    assert record["httpStatus"] == 429
    assert record["providerHttpRequestAttempts"] == 2
    assert record["retryAutomatically"] is False
    assert secret not in json.dumps(record)
    store.store_provider_failure_diagnostic("dr-test", record)
    assert store.get_provider_failure_diagnostic("dr-test") == record
    with pytest.raises(IdempotencyConflict):
        store.store_provider_failure_diagnostic("dr-test", {**record, "httpStatus": 500})
    store.close()
    raw = (tmp_path / "capt-ledger.db").read_bytes()
    assert b"sk-proj_" not in raw
    assert b"PROVIDER_HTTP_ERROR" not in raw
    reopened = _db(tmp_path)
    q = RuntimeQueryService(reopened)
    result = q.handle({"op": "provider_failure_diagnostic", "driverRunId": "dr-test"})
    assert result["ok"] and result["result"] == record
    assert q.handle({"op": "provider_failure_diagnostic", "driverRunId": "../bad"})["ok"] is False
    reopened.close()


def test_malicious_exception_fields_fail_to_become_diagnostic_content():
    class Untrusted(Exception):
        diagnostic_code = "sk_fake-data"
        diagnostic_phase = "attacker_phase"
        http_status = "429; unexpected"
    result = safe_provider_failure(
        Untrusted("Bearer SUPER_SECRET provider prompt body"),
        driver_run_id="dr-bad", model="extreme model secret",
        provider="attacker-controlled.example",
        dispatch_boundary="garbage",
    )
    assert result["failureCode"] == "PROVIDER_UNCLASSIFIED_FAILURE"
    assert result["phase"] == "unknown"
    assert result["httpStatus"] is None
    assert result["provider"] == "other"
    assert result["dispatchBoundary"] == "unknown"
    assert "SUPER_SECRET" not in json.dumps(result)
    assert "attacker-controlled.example" not in json.dumps(result)


def test_council_survives_restart_with_partial_receipt_and_never_auto_replays(tmp_path):
    s = _db(tmp_path)
    members = [{"cohortId": "cohort-a", "driverRunId": "dr-a"},
               {"cohortId": "cohort-b", "driverRunId": "dr-b"}]
    record, created = s.begin_council_receipt("council-1", "sha256:abc", "cmd-1", members, "2026-10-08T08:00:00Z")
    assert created and record["state"] == "in_progress"
    a = safe_cohort_receipt("cohort-a", {"driverRunId":"dr-a","missionId":"m-a"},
                            {"status":"rejected", "classification":"internal_failure",
                             "detail":"Bearer SECRET LEAK",
                             "error":{"code":"PROVIDERDRIVERFAILURE","category":"internal_failure"},
                             "result":{}})
    s.record_council_member_receipt("council-1", a, "2026-10-08T08:01:00Z")
    s.close()
    again = _db(tmp_path)
    q = RuntimeQueryService(again)
    partial = q.handle({"op":"council_receipt","councilId":"council-1"})["result"]
    assert partial["cohorts"][0]["errorCode"] == "PROVIDERDRIVERFAILURE"
    assert partial["cohorts"][1]["status"] == "pending"
    assert partial["complete"] is False and partial["state"] == "in_progress"
    assert partial["replayForbidden"] is True
    assert "SECRET LEAK" not in json.dumps(partial)
    replay, created = again.begin_council_receipt("council-1", "sha256:abc", "cmd-2", members, "2026-10-08T09:00:00Z")
    assert created is False and replay == partial
    with pytest.raises(IdempotencyConflict):
        again.begin_council_receipt("council-1", "sha256:different", "cmd-2", members,
                                    "2026-10-08T09:00:00Z")
    b = safe_cohort_receipt("cohort-b", {"driverRunId":"dr-b","missionId":"m-b"},
                            {"status":"accepted","result":{"artifactCandidate":{
                                "artifactDigest":"sha256:"+"a"*64,
                                "artifactPath":"/secret/SHOULD_NOT_STORE.md"}}})
    terminal = again.record_council_member_receipt("council-1", b, "2026-10-08T09:03:00Z")
    assert terminal["complete"] is True and terminal["state"] == "terminal"
    assert terminal["cohorts"][1]["artifactDigest"] == "sha256:"+"a"*64
    assert "/secret/" not in json.dumps(terminal)
    with pytest.raises(IdempotencyConflict):
        again.record_council_member_receipt("council-1", {**b, "status":"rejected"}, "2026-10-08T09:04:00Z")
    again.close()


def test_concurrent_cohort_settlement_is_atomic(tmp_path):
    s = _db(tmp_path)
    members = [{"cohortId":f"cohort-{i}","driverRunId":f"dr-{i}"} for i in range(8)]
    s.begin_council_receipt("council-concurrent", "sha256:abc", "cmd-1", members,
                            "2026-10-08T00:00:00Z")
    def settle(i):
        member = safe_cohort_receipt(f"cohort-{i}", {"driverRunId":f"dr-{i}"},
                                      {"status":"rejected","error":{"code":"PROVIDERDRIVERFAILURE"}})
        s.record_council_member_receipt("council-concurrent", member, "2026-10-08T01:00:00Z")
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(settle, range(8)))
    receipt = s.get_council_receipt("council-concurrent")
    assert receipt["complete"] and len(receipt["cohorts"]) == 8
    assert all(x["status"]=="rejected" for x in receipt["cohorts"])
    s.close()


def test_governed_council_is_idempotent_and_retrievable(tmp_path):
    store = _db(tmp_path)
    svc = RuntimeCommandService(store, "operator-test", "session-test")
    original_execute = svc.execute
    calls = []
    def simulated_approved_execution(cmd):
        if cmd["op"] == "run_approved_hermes_inspection":
            calls.append(cmd["payload"]["cohortSpec"]["cohortId"])
            return svc._receipt(
                cmd, status="rejected", classification="internal_failure",
                error={"category":"internal_failure", "code":"PROVIDERDRIVERFAILURE"},
                detail="API_KEY=NOT_STORED",
            )
        return original_execute(cmd)
    svc.execute = simulated_approved_execution
    payload = {"councilId":"council-governed-unit",
               "maxConcurrentCohorts":2, "executions":[
                 {"cohortSpec":{"cohortId":f"cohort-{i}", "vesselsPerCohort":2,
                                "configurationId":"review-v1",
                                "vesselCharterPolicy":default_charter_policy(2)},
                  "driverRunId":f"dr-{i}", "missionId":f"m-{i}", "approvalRequestId":f"approval-{i}"}
                 for i in range(2)
               ]}
    cmd = {
        "commandId":"cmd-test", "operatorId":"operator-test",
        "sessionId":"session-test", "schemaVersion":"1.0.0",
        "correlationId":"corr-test", "idempotencyKey":"idem-test",
        "timestamp":"2026-10-08T00:00:00Z",
        "op":"run_approved_council_inspection", "payload":payload,
    }
    returned = svc.execute(cmd)
    assert returned["status"] == "accepted", returned
    assert sorted(calls) == ["cohort-0", "cohort-1"]
    result = RuntimeQueryService(store).handle({
        "op":"council_receipt","councilId":"council-governed-unit",
    })["result"]
    assert result["complete"] and len(result["cohorts"]) == 2
    assert all(x["errorCode"]=="PROVIDERDRIVERFAILURE" for x in result["cohorts"])
    assert "API_KEY=" not in json.dumps(result)
    repeated = svc.execute({**cmd,"commandId":"cmd-new","idempotencyKey":"idem-new"})
    assert repeated["status"] == "idempotent"
    assert len(calls) == 2
    store.close()

def test_http_failure_exposes_status_not_upstream_body(tmp_path, monkeypatch):
    import io
    import time
    import urllib.error
    from capt_runtime.drivers.provider import ProviderDriver
    from capt_runtime.resource_governor import TokenCostGovernor

    secret = "Bearer SK_SECRET_DO_NOT_RECORD"
    response = urllib.error.HTTPError(
        "https://provider.example.invalid/chat/completions", 429,
        "provider rejected: " + secret, {"x-hidden-token": secret},
        io.BytesIO(secret.encode()),
    )
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(response))
    governor = TokenCostGovernor(max_requests_per_session=2)
    driver = ProviderDriver(
        str(tmp_path), provider_id="openrouter", model="test/model",
        base_url="https://provider.example.invalid", governor=governor,
    )
    driver.runs["run"] = {"state":"running","dispatchBoundary":"prepared"}
    driver._request_deadlines["run"] = time.monotonic() + 20
    with pytest.raises(ProviderDriverFailure) as caught:
        driver._post_json("run", driver.base_url+"/chat/completions", {}, {})
    assert caught.value.diagnostic_code == "PROVIDER_HTTP_ERROR"
    assert caught.value.http_status == 429
    record = safe_provider_failure(
        caught.value, driver_run_id="dr-a", model="test/model", provider="openrouter",
        dispatch_boundary="request_started", request_attempts=1,
    )
    assert record["httpStatus"] == 429
    assert secret not in json.dumps(record)
    assert secret not in str(caught.value)
    assert governor.snapshot()["consumedRequests"] == 1


def test_two_turn_failure_no_automatic_retry_and_explained_phase(tmp_path, monkeypatch):
    import time
    import urllib.error
    from capt_runtime.drivers.provider import ProviderDriver
    from capt_runtime.resource_governor import TokenCostGovernor

    calls = []
    class Response:
        def read(self): return b'{"choices":[{"message":{"content":"done"}}],"usage":{"prompt_tokens":3,"completion_tokens":4}}'
        def close(self): return None

    def fake_urlopen(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise urllib.error.URLError("secret DNS value")
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    governor = TokenCostGovernor(max_requests_per_session=2)
    driver = ProviderDriver(
        str(tmp_path), provider_id="openrouter", model="test/model",
        base_url="https://provider.example.invalid", governor=governor,
    )
    driver.runs["run"] = {"state":"running","dispatchBoundary":"prepared"}
    driver._request_deadlines["run"] = time.monotonic() + 20
    assert driver._post_json("run", driver.base_url+"/chat/completions", {}, {})["choices"]
    with pytest.raises(ProviderDriverFailure) as raised:
        driver._post_json("run", driver.base_url+"/chat/completions", {}, {})
    assert raised.value.diagnostic_code == "PROVIDER_NETWORK_ERROR"
    assert raised.value.diagnostic_phase == "response_headers"
    assert len(calls) == 2
    assert governor.snapshot()["consumedRequests"] == 2
    record = safe_provider_failure(
        raised.value, driver_run_id="dr-a", model="test/model", provider="openrouter",
        dispatch_boundary="request_started", request_attempts=2)
    assert record["failureCode"] == "PROVIDER_NETWORK_ERROR"
    assert "secret DNS value" not in json.dumps(record)
    assert record["retryAutomatically"] is False
