"""No inference network tests: exact OpenRouter model preflight and fail closed."""
import asyncio
import io
import json
from pathlib import Path
import urllib.error

import pytest

from capt_runtime import provider_model_preflight as preflight
from capt_runtime.drivers.provider import ProviderDriver, ProviderDriverFailure


class _JsonResponse:
    def __init__(self,payload):
        self.payload=json.dumps(payload).encode()
    def __enter__(self):return self
    def __exit__(self,*_a):pass
    def read(self,n=-1):return self.payload[:n]


def test_catalog_get_is_read_only_exact_origin_no_prompt(monkeypatch):
    seen=[]
    def fake(req,*,timeout):
        seen.append((req.get_full_url(),req.get_method(),dict(req.header_items()),timeout))
        return _JsonResponse({"data":{"id":"deepseek/deepseek-v4.1-flash-1017","context_length":1048576}})
    monkeypatch.setattr(preflight.http_client,"open_url",fake)
    receipt=preflight.verify_openrouter_model("deepseek/deepseek-v4.1-flash-1017",api_key="fixture",modality="text")
    assert receipt=={"model":"deepseek/deepseek-v4.1-flash-1017","modality":"text","available":True}
    assert len(seen)==1
    url,method,headers,timeout=seen[0]
    assert url=="https://openrouter.ai/api/v1/model/deepseek/deepseek-v4.1-flash-1017"
    assert method=="GET"
    assert timeout==6.0
    assert "fixture" not in url


def test_model_404_is_classified_before_inference(monkeypatch,tmp_path):
    def fake(req,*,timeout):
        raise urllib.error.HTTPError(req.full_url,404,"not found",{},io.BytesIO(b"upstream details"))
    monkeypatch.setattr(preflight.http_client,"open_url",fake)
    driver=ProviderDriver(str(tmp_path/"stage"),provider_id="openrouter",
                          model="deepseek/deepseek-v4.1-flash-1017",
                          base_url="https://openrouter.ai/api/v1",api_key="fixture",
                          dispatch_prompt="Synthetic no-cost fixture")
    monkeypatch.setattr(driver,"_post_json",lambda *args,**kw: pytest.fail("provider inference POST must not run"))
    with pytest.raises(ProviderDriverFailure) as failure:
        asyncio.run(driver.submit({"driverRunId":"dr-preflight-404","missionId":"m","taskId":"t","contextSlice":{}}))
    assert failure.value.diagnostic_code=="PROVIDER_MODEL_UNAVAILABLE"
    assert failure.value.http_status==404
    assert driver.runs["dr-preflight-404"]["state"]=="failed"
    assert driver.runs["dr-preflight-404"]["dispatchBoundary"]=="prepared"


def test_metadata_402_fails_before_inference(monkeypatch,tmp_path):
    def fake(req,*,timeout):
        raise urllib.error.HTTPError(req.full_url,402,"insufficient",{},io.BytesIO(b"provider error"))
    monkeypatch.setattr(preflight.http_client,"open_url",fake)
    driver=ProviderDriver(str(tmp_path/"stage"),provider_id="openrouter",
                          model="deepseek/deepseek-v4.1-flash",base_url="https://openrouter.ai/api/v1",
                          api_key="fixture",dispatch_prompt="fixture")
    monkeypatch.setattr(driver,"_post_json",lambda *args,**kw:pytest.fail("inference POST not allowed"))
    with pytest.raises(ProviderDriverFailure) as failure:
        asyncio.run(driver.submit({"driverRunId":"dr-preflight-402","missionId":"m","taskId":"t","contextSlice":{}}))
    assert failure.value.diagnostic_code=="PROVIDER_ACCOUNT_UNAVAILABLE"
    assert failure.value.http_status==402


def test_image_adapter_catalog_must_match_output_modality(monkeypatch):
    monkeypatch.setattr(preflight.http_client,"open_url",
        lambda req,*,timeout:_JsonResponse({"data":[
            {"id":"image/not-generation","architecture":{"output_modalities":["text"]}},
            {"id":"image/proper","architecture":{"output_modalities":["image"]}},
        ]}))
    assert preflight.verify_openrouter_model("image/proper",api_key="fixture",modality="image")["available"]
    with pytest.raises(preflight.ProviderModelPreflightError,match="UNAVAILABLE"):
        preflight.verify_openrouter_model("image/not-generation",api_key="fixture",modality="image")


@pytest.mark.parametrize("model",["","../../escape","evil/test/extra","space name/model","evil/%2f"])
def test_bad_model_ids_do_not_emit_http(monkeypatch,model):
    monkeypatch.setattr(preflight.http_client,"open_url",
        lambda *a,**kw:pytest.fail("invalid model must not call HTTP"))
    with pytest.raises(preflight.ProviderModelPreflightError,match="INVALID"):
        preflight.verify_openrouter_model(model,api_key="fixture")


def test_uncertain_metadata_failure_is_not_blindly_billed(monkeypatch):
    monkeypatch.setattr(preflight.http_client,"open_url",
        lambda *a,**kw:(_ for _ in ()).throw(TimeoutError("timeout")))
    with pytest.raises(preflight.ProviderModelPreflightError,match="UNAVAILABLE"):
        preflight.verify_openrouter_model("deepseek/deepseek-v4.1-flash",api_key="fixture")


def test_preflight_never_downgrades_unrelated_local_provider(monkeypatch,tmp_path):
    driver=ProviderDriver(str(tmp_path/"stage"),provider_id="mtplx",
                          model="local/test",base_url="https://example.invalid/v1",dispatch_prompt="fixture")
    monkeypatch.setattr(preflight.http_client,"open_url",
        lambda *a,**kw:pytest.fail("local models must not contact OpenRouter metadata"))
    monkeypatch.setattr(driver,"_post_json",lambda *args,**kw:{
        "choices":[{"message":{"content":"LOCAL_TEST_OK"},"finish_reason":"stop"}],
        "usage":{"prompt_tokens":2,"completion_tokens":2},
    })
    result=asyncio.run(driver.submit({"driverRunId":"dr-local-proof","missionId":"m","taskId":"t","contextSlice":{}}))
    assert result["state"]=="completed"
