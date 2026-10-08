"""Exact-host image URL generation variants; no uncontrolled asset fetch."""
import json
from pathlib import Path
import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.media_adapter_contract import MediaAdapterContract
from capt_runtime.media_execution import (
    MediaRoute, MediaRouteRegistry, prepare_media_approval,
    submit_approved_media
)
from tests.capt_runtime.test_media_execution import service, metadata, approve


def route():
    return MediaRoute(
        adapter_id="image-url-fixture", provider="image-provider",
        model="fixture-model", maximum_price_usd=0.01,
        contract=MediaAdapterContract(
            provider_id="image-provider", origin="https://api.example.org",
            operation="image_generate", transport="json",
            submit_path="/v1/images/generations", response_type="json_url",
            media_types=("image/png",),
            download_origins=("https://cdn.example.org",),
        )
    )


class FakeTransport:
    def __init__(self, response_url):
        self.requests = []
        self.response_url = response_url
    def send(self, method, url, body, headers, limit):
        self.requests.append((method, url, body, headers))
        if method == "POST":
            return json.dumps({"data":[{"url":self.response_url}]}).encode(), "application/json"
        assert method == "GET"
        return b"\x89PNG\r\n\x1a\nfixture", "image/png"


def prepare(svc):
    r = route()
    registry = MediaRouteRegistry({r.adapter_id:r})
    req = prepare_media_approval(svc, {
        "operation":"image_generate", "provider":r.provider,
        "model":r.model, "adapterId":r.adapter_id,
        "providerNetworkPolicy":"remote_allowed", "maxCostUSD":0.01,
        "prompt":"Make one safe fixture image", "files":[]
    }, metadata("prepare"), registry=registry)
    approve(svc, req)
    return registry, req


def test_allowlisted_image_url_download_no_cross_origin_credentials(tmp_path):
    svc = service(tmp_path)
    reg, req = prepare(svc)
    fake = FakeTransport("https://cdn.example.org/result.png?token=short-lived")
    receipt = submit_approved_media(
        svc, req["requestId"], metadata("run"), registry=reg,
        transport=fake, credential_resolver=lambda _: "secret-fixture"
    )
    assert receipt["state"] == "completed"
    assert receipt["artifactCandidate"]["mediaType"] == "image/png"
    assert Path(receipt["artifactCandidate"]["artifactPath"]).read_bytes().startswith(b"\x89PNG")
    assert [r[0] for r in fake.requests] == ["POST", "GET"]
    assert json.loads(fake.requests[0][2])["response_format"] == "url"
    assert fake.requests[0][3] == {
        "Authorization": "Bearer secret-fixture",
        "Content-Type": "application/json"
    }
    assert fake.requests[1][3] == {}, "Bearer token must not be sent to a distinct CDN"
    assert "token=short-lived" not in str(receipt)
    receipt2 = submit_approved_media(
        svc, req["requestId"], metadata("retry"), registry=reg,
        transport=fake, credential_resolver=lambda _: "secret-fixture"
    )
    assert receipt2["state"] == "completed"
    assert len(fake.requests) == 2, "Must not repeat generation or download"
    svc.store.close()


@pytest.mark.parametrize("url", [
    "http://169.254.169.254/latest/meta-data",
    "https://evil.example.net/result.png",
    "file:///etc/passwd",
    "https://cdn.example.org@evil.example.net/image.png",
])
def test_untrusted_generation_urls_are_refused_before_get(tmp_path,url):
    svc = service(tmp_path)
    registry, request = prepare(svc)
    http = FakeTransport(url)
    with pytest.raises(AuthorityViolation, match="MEDIA_IMAGE_URL_ORIGIN_REFUSED"):
        submit_approved_media(svc, request["requestId"], metadata("run"),
                              registry=registry, transport=http,
                              credential_resolver=lambda _: "secret")
    assert [r[0] for r in http.requests] == ["POST"]
    svc.store.close()


def test_url_style_without_explicit_download_origin_not_configurable():
    r = route()
    invalid = MediaRoute(
        adapter_id=r.adapter_id, provider=r.provider, model=r.model,
        maximum_price_usd=r.maximum_price_usd,
        contract=MediaAdapterContract(
            provider_id=r.provider, origin=r.contract.origin,
            operation="image_generate", transport="json",
            submit_path="/v1/images/generations", response_type="json_url",
            media_types=("image/png",)
        )
    )
    with pytest.raises(AuthorityViolation, match="MEDIA_IMAGE_URL_REQUIRES_DOWNLOAD_ALLOWLIST"):
        invalid.validate()
