"""Adversarial, zero-network OpenRouter typed error and secret safety tests."""
import asyncio
import io
import json
import urllib.error

import pytest

from capt_runtime import provider_error_types
from capt_runtime.diagnostic_receipts import safe_provider_failure, safe_cohort_receipt
from capt_runtime.drivers import provider as provider_module
from capt_runtime.drivers.provider import ProviderDriver, ProviderDriverFailure


class _Response:
    def __init__(self, body):
        self.body=json.dumps(body).encode()
    def read(self):
        return self.body
    def close(self):
        return None


def _driver(monkeypatch, tmp_path, monkey_response):
    # No external metadata GET and no actual provider POST in these fixtures.
    monkeypatch.setattr(provider_module, "verify_openrouter_model",
        lambda model, **kw: {"model": model, "available": True})
    def open_url(req, *, timeout):
        assert req.full_url == "https://openrouter.ai/api/v1/chat/completions"
        assert req.get_method() == "POST"
        return monkey_response(req)
    monkeypatch.setattr(provider_module.http_client, "open_url", open_url)
    return ProviderDriver(
        str(tmp_path/"staging"),provider_id="openrouter",
        model="deepseek/deepseek-v4-flash",
        base_url="https://openrouter.ai/api/v1",
        api_key="do-not-persist-this-key",
        dispatch_prompt="Do not leak prompt: SECRET_TEST_VALUE",
    )


def _execute(driver):
    return asyncio.run(driver.submit({
        "driverRunId": "dr-read-only-typed-test",
        "missionId": "m-test", "taskId": "t-test",
        "contextSlice": {"budgets":{"maxSeconds":30,"maxTokens":64000}},
    }))


def test_actual_http404_keeps_safe_openrouter_not_found_type(monkeypatch,tmp_path):
    secret="SECRET_FROM_OPENROUTER_BODY"
    def failure(req):
        body=json.dumps({"error":{
            "code":404,
            "message":"Model not found, "+secret,
            "metadata":{"error_type":"not_found","provider_code":secret,"raw":secret},
        }}).encode()
        raise urllib.error.HTTPError(req.full_url,404,"not found",{},io.BytesIO(body))
    driver=_driver(monkeypatch,tmp_path,failure)
    with pytest.raises(ProviderDriverFailure) as caught:
        _execute(driver)
    e=caught.value
    assert e.diagnostic_code=="PROVIDER_HTTP_ERROR"
    assert e.diagnostic_phase=="response_headers"
    assert e.http_status==404
    assert e.provider_error_type=="not_found"
    record=safe_provider_failure(e,driver_run_id="dr-typed-404",provider="openrouter",
        model="deepseek/deepseek-v4-flash",dispatch_boundary="request_started",
        request_attempts=1)
    assert record["providerErrorType"]=="not_found"
    assert record["retryAutomatically"] is False
    assert secret not in json.dumps(record)
    assert "SECRET_TEST_VALUE" not in json.dumps(record)
    assert not list((tmp_path/"staging").glob("provider-analysis*"))
    cohort=safe_cohort_receipt("cohort-a",{"driverRunId":"dr-typed-404"},
        {"status":"rejected"},failure_diagnostic=record)
    assert cohort["sanitizedProviderErrorType"]=="not_found"
    assert secret not in json.dumps(cohort)


def test_oversized_or_arbitrary_error_type_is_never_persisted(monkeypatch,tmp_path):
    secret="SECRET_FROM_PROVIDER_MALICIOUS_CODE"
    def failure(req):
        body=json.dumps({"error":{"message":secret,
            "metadata":{"error_type":secret}}}).encode()+b"z"*9000
        raise urllib.error.HTTPError(req.full_url,404,"not found",{},io.BytesIO(body))
    driver=_driver(monkeypatch,tmp_path,failure)
    with pytest.raises(ProviderDriverFailure) as caught:
        _execute(driver)
    assert caught.value.provider_error_type is None
    record=safe_provider_failure(caught.value,driver_run_id="dr-malicious",
        provider="openrouter",model="deepseek/deepseek-v4-flash",
        dispatch_boundary="request_started")
    assert record["providerErrorType"] is None
    assert secret not in json.dumps(record)


@pytest.mark.parametrize("error_shape",[
    {"error":{"code":502,"message":"sensitive text",
             "metadata":{"error_type":"provider_unavailable",
                         "provider_code":"secret"}}},
    {"choices":[{"finish_reason":"error","message":{"content":"partial"},
                "error":{"code":502,"message":"secret",
                         "metadata":{"error_type":"provider_unavailable"}}}]},
])
def test_http200_with_embedded_error_is_not_success(monkeypatch,tmp_path,error_shape):
    driver=_driver(monkeypatch,tmp_path,lambda req:_Response(error_shape))
    with pytest.raises(ProviderDriverFailure) as caught:
        _execute(driver)
    e=caught.value
    assert e.diagnostic_code=="PROVIDER_UPSTREAM_ERROR"
    assert e.diagnostic_phase=="response_body"
    assert e.provider_error_type=="provider_unavailable"
    record=safe_provider_failure(e,driver_run_id="dr-embedded",
        provider="openrouter",model="deepseek/deepseek-v4-flash",
        dispatch_boundary="response_completed")
    assert record["providerErrorType"]=="provider_unavailable"
    assert "secret" not in json.dumps(record)
    assert not list((tmp_path/"staging").glob("provider-analysis*"))


def test_non_openrouter_service_does_not_promote_provider_codes():
    e=ProviderDriverFailure("SECRET",diagnostic_code="PROVIDER_UPSTREAM_ERROR",
        provider_error_type="not_found")
    d=safe_provider_failure(e,driver_run_id="dr-openai",
        provider="openai",model="some/model",dispatch_boundary="response_completed")
    assert d["providerErrorType"] is None


def test_rejects_untrusted_error_metadata_recursively():
    for data in [None, "sk-token", {"error":"bad"},
            {"error":{"metadata":{"error_type":"secret-api-key"}}},
            {"error":{"metadata":{"error_type":{"payload":"secret"}}}}]:
        assert provider_error_types.openrouter_error_type(data) is None
    assert provider_error_types.openrouter_embedded_error({
        "choices":[{"finish_reason":"error","error":{"metadata":{
            "error_type":"not_found"}}}]})==(True,"not_found")
