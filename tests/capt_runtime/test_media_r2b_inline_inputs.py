"""Gemini typed inline PDF/video, with approval and digest before HTTP.

No external calls, provider secrets, billable inference or actual video decode.
"""
from __future__ import annotations
import base64
import hashlib
import json
from pathlib import Path
import uuid
import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.media_adapter_contract import MediaAdapterContract
from capt_runtime.media_execution import (
    MediaRoute, MediaRouteRegistry, prepare_media_approval,
    submit_approved_media, _build_request, _result_bytes
)
from tests.capt_runtime.test_media_execution import service, metadata, approve, FakeHTTP


def route(operation: str) -> MediaRoute:
    return MediaRoute(
        adapter_id="gemini-typed-" + operation,
        provider="gemini-local-fixture", model="gemini-test", maximum_price_usd=0.01,
        auth_style="x-goog-api-key",
        contract=MediaAdapterContract(
            provider_id="gemini-local-fixture",
            origin="https://generativelanguage.googleapis.com",
            operation=operation,
            transport="gemini_interactions",
            submit_path="/v1beta/interactions",
            response_type="json_text",
            media_types=("application/pdf",) if operation == "document_input" else ("video/mp4",)
        )
    )


def staged(tmp_path: Path, payload: bytes, name: str, mime: str) -> dict:
    folder = tmp_path / "native-media-intake" / "v1" / str(uuid.uuid4())
    folder.mkdir(parents=True)
    target = folder / (str(uuid.uuid4()) + "-" + name)
    target.write_bytes(payload)
    return {"stagedPath": str(target), "sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
            "sizeBytes": len(payload), "mediaType": mime, "originalName": name}


@pytest.mark.parametrize(("operation", "bytes_", "name", "mime", "block"), [
    ("document_input", b"%PDF-1.5\n1 0 obj\nendobj", "file.pdf", "application/pdf", "document"),
    ("video_input", b"\x00\x00\x00\x18ftypisom" + bytes(100), "clip.mp4", "video/mp4", "video"),
])
def test_typed_media_bytes_reach_governed_endpoint_once(
    tmp_path, operation, bytes_, name, mime, block
):
    svc = service(tmp_path)
    item = staged(tmp_path, bytes_, name, mime)
    configured = route(operation)
    registry = MediaRouteRegistry({configured.adapter_id: configured})
    req = prepare_media_approval(
        svc, {"operation": operation, "provider": configured.provider,
              "model": configured.model, "adapterId": configured.adapter_id,
              "providerNetworkPolicy": "remote_allowed", "maxCostUSD": 0.02,
              "prompt": "Describe precisely what the file contains.", "files": [item]},
        metadata("prepare"), registry=registry)
    remote = FakeHTTP(operation, b'{"status":"completed","output_text":"fixture analyzed"}')
    with pytest.raises(AuthorityViolation):
        submit_approved_media(svc, req["requestId"], metadata("deny"),
                              registry=registry, transport=remote,
                              credential_resolver=lambda _: "fixture")
    assert remote.requests == []
    approve(svc, req)
    outcome = submit_approved_media(svc, req["requestId"], metadata("submit"),
                                    registry=registry, transport=remote,
                                    credential_resolver=lambda _: "fixture")
    assert outcome["state"] == "completed"
    assert len(remote.requests) == 1
    method, url, raw, headers, _ = remote.requests[0]
    assert method == "POST"
    assert url == "https://generativelanguage.googleapis.com/v1beta/interactions"
    assert headers["x-goog-api-key"] == "fixture"
    body = json.loads(raw)
    assert body["model"] == "gemini-test"
    assert body["input"][0] == {"type": "text", "text": "Describe precisely what the file contains."}
    assert body["input"][1]["type"] == block
    assert body["input"][1]["mime_type"] == mime
    assert base64.b64decode(body["input"][1]["data"], validate=True) == bytes_
    assert outcome["resultText"] == "fixture analyzed"
    again = submit_approved_media(svc, req["requestId"], metadata("duplicate"),
                                  registry=registry, transport=remote,
                                  credential_resolver=lambda _: "fixture")
    assert again["state"] == "completed"
    assert len(remote.requests) == 1
    svc.store.close()


def test_pdf_signature_mismatch_blocks_admission(tmp_path):
    svc = service(tmp_path)
    configured = route("document_input")
    item = staged(tmp_path, b"not-a-pdf", "filename.pdf", "application/pdf")
    with pytest.raises(AuthorityViolation, match="MEDIA_INPUT_SIGNATURE_MISMATCH"):
        prepare_media_approval(
            svc, {"operation": "document_input", "provider": configured.provider,
                  "model": configured.model, "adapterId": configured.adapter_id,
                  "providerNetworkPolicy": "remote_allowed", "maxCostUSD": 0.02,
                  "prompt": "Explain this file", "files": [item]},
            metadata("prepare"),
            registry=MediaRouteRegistry({configured.adapter_id: configured})
        )
    svc.store.close()


def test_gemini_nonterminal_and_unrecognized_responses_are_never_success():
    with pytest.raises(AuthorityViolation, match="NOT_COMPLETED"):
        _result_bytes("video_input", b'{"status":"in_progress","id":"secret"}', "json_text")
    with pytest.raises(AuthorityViolation, match="TEXT_MISSING"):
        _result_bytes("document_input", b'{"status":"completed"}', "json_text")
    data, mime, op = _result_bytes("document_input", b'{"status":"completed","output_text":"summary"}', "json_text")
    assert data == b"summary" and mime == "text/plain" and op is None
    data, mime, op = _result_bytes("video_input",
        b'{"status":"completed","outputs":[{"type":"text","text":"video summary"}]}', "json_text")
    assert (data, mime, op) == (b"video summary", "text/plain", None)


def test_inline_total_size_remains_governed_and_no_unlisted_wire_route():
    configured = route("video_input")
    configured.validate()
    assert configured.contract.transport == "gemini_interactions"
    fake = MediaRoute(
        adapter_id="unsafe", provider=configured.provider, model=configured.model,
        contract=MediaAdapterContract(
            provider_id=configured.provider, origin=configured.contract.origin,
            operation="document_input", transport="chat_completions",
            submit_path="/v1beta/interactions", response_type="json_text",
            media_types=("application/pdf",)
        )
    )
    with pytest.raises(AuthorityViolation, match="MEDIA_ROUTE_WIRE_FORMAT_NOT_IMPLEMENTED"):
        fake.validate()


def test_large_video_requires_separate_upload_protocol(tmp_path):
    from capt_runtime.media_execution import MAX_INLINE_BYTES
    svc = service(tmp_path)
    configured = route("video_input")
    # Sparse local fixture avoids allocating a video-sized byte array.
    folder = tmp_path / "native-media-intake" / "v1" / str(uuid.uuid4())
    folder.mkdir(parents=True)
    target = folder / (str(uuid.uuid4()) + "-oversize.mp4")
    with target.open("wb") as stream:
        stream.write(b"\x00\x00\x00\x18ftypisom")
        stream.truncate(MAX_INLINE_BYTES + 1)
    file = {
        "stagedPath": str(target), "sizeBytes": MAX_INLINE_BYTES + 1,
        "sha256": "sha256:" + hashlib.sha256(target.read_bytes()).hexdigest(),
        "mediaType": "video/mp4", "originalName": "oversize.mp4"
    }
    with pytest.raises(AuthorityViolation, match="MEDIA_INPUT_OVER_SIZE_LIMIT"):
        prepare_media_approval(
            svc, {"operation": "video_input", "provider": configured.provider,
                  "model": configured.model, "adapterId": configured.adapter_id,
                  "providerNetworkPolicy": "remote_allowed", "maxCostUSD": 0.02,
                  "prompt": "Analyze large video", "files": [file]},
            metadata("prepare"),
            registry=MediaRouteRegistry({configured.adapter_id: configured}),
        )
    svc.store.close()
