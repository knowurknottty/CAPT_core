"""Media routing declarations only. No HTTP operation may occur here."""
import pytest

from capt_runtime.media_adapter_contract import MediaAdapterContract


def image():
    return MediaAdapterContract(
        provider_id="openai-image",
        origin="https://api.openai.com",
        operation="image_generate",
        transport="json",
        submit_path="/v1/images/generations",
        response_type="json_base64",
        media_types=("image/png", "image/webp"),
    )


def video():
    return MediaAdapterContract(
        provider_id="video-special",
        origin="https://api.example.org",
        operation="video_generate",
        transport="async_job",
        submit_path="/v1/video/create",
        poll_path="/v1/jobs/{job_id}",
        result_path="/v1/jobs/{job_id}/assets",
        response_type="job_receipt",
        media_types=("video/mp4",),
        download_origins=("https://media.example.org",),
    )


def test_image_generation_profile_is_structurally_valid():
    image().validate()


def test_async_nonstandard_video_job_is_declared_without_dispatch():
    contract = video()
    contract.validate()
    assert contract.permits_download(
        "https://media.example.org/results/video.mp4?signature=opaque"
    )
    assert not contract.permits_download(
        "https://api.example.org/v1/metadata?signature=opaque"
    )


@pytest.mark.parametrize("origin", [
    "http://api.example.org", "http://127.0.0.1:8000",
    "https://user:secret@api.example.org",
    "https://api.example.org/path", "https://api.example.org/?token=secret",
    "file:///etc/passwd", "https://192.168.1.12",
    "https://api.example.org:notaport",
])
def test_unsafe_origins_are_rejected(origin):
    bad = MediaAdapterContract(
        provider_id="unsafe", origin=origin, operation="image_generate",
        transport="json", submit_path="/v1/images/generations",
        response_type="json_base64", media_types=("image/png",)
    )
    with pytest.raises(ValueError):
        bad.validate()


@pytest.mark.parametrize("path", [
    "https://evil.example.org/upload", "//evil.example.org/payload",
    "/v1/../secrets", "/v1/%2e%2e/secrets",
    "/v1/data?api_key=secret", "/v1/jobs/{freeform_url}",
    "/v1/%252e%252e/secrets",
])
def test_unsafe_paths_refused(path):
    contract = MediaAdapterContract(
        provider_id="bad-path", origin="https://api.example.org",
        operation="video_generate", transport="async_job",
        submit_path="/v1/create", poll_path=path,
        result_path="/v1/jobs/{job_id}/assets",
        response_type="job_receipt", media_types=("video/mp4",),
    )
    with pytest.raises(ValueError):
        contract.validate()


def test_private_download_host_and_unrelated_signed_asset_denied():
    contract = video()
    assert not contract.permits_download("https://169.254.169.254/latest/meta-data/")
    assert not contract.permits_download("file:///private/etc/hosts")
    assert not contract.permits_download("https://unrelated.example.net/video.mp4")
    assert not contract.permits_download("https://media.example.org@evil.example.com/video.mp4")


def test_async_transport_requires_explicit_poll_and_receipt_schema():
    invalid = MediaAdapterContract(
        provider_id="missing-poll",
        origin="https://api.example.org", operation="video_generate",
        transport="async_job", submit_path="/start",
        response_type="job_receipt", media_types=("video/mp4",),
    )
    with pytest.raises(ValueError, match="POLL_AND_RESULT"):
        invalid.validate()


def test_private_loopback_only_when_explicitly_allowed():
    local = MediaAdapterContract(
        provider_id="local-media", origin="http://127.0.0.1:9000",
        operation="image_generate", transport="json",
        submit_path="/generate", response_type="raw_binary",
        media_types=("image/png",), allow_loopback=True,
    )
    local.validate()
