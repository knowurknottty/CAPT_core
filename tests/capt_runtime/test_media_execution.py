"""Offline, no-cost media authority, dispatch and restart tests."""
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

import pytest

from capt_runtime import commands
from capt_runtime.errors import AuthorityViolation
from capt_runtime.media_adapter_contract import MediaAdapterContract
from capt_runtime.media_execution import (
    MediaRoute, MediaRouteRegistry, media_job_status,
    prepare_media_approval, submit_approved_media,
)
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore


def metadata(op="test", key=None):
    key = key or ("media-test-" + uuid.uuid4().hex)
    return commands.command(
        command_id="cmd-" + uuid.uuid4().hex,
        idempotency_key=key, operation_fingerprint=commands.fingerprint(op, {"key": key}),
        correlation_id="corr-" + uuid.uuid4().hex,
        actor_id="operator-test", actor_kind="human",
        issued_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        replay_policy="never"
    )


def route(operation, *, provider="mock-provider", model="mock-model"):
    return MediaRoute(
        adapter_id="mock-" + operation,
        provider=provider, model=model,
        maximum_price_usd=0.4,
        contract=MediaAdapterContract(
            provider_id=provider, origin="https://api.example.org",
            operation=operation,
            transport="async_job" if operation == "video_generate" else
                ("multipart" if operation == "audio_transcribe" else
                  "chat_completions" if operation == "image_input" else "json"),
            submit_path="/v1/media/" + operation,
            response_type="job_receipt" if operation == "video_generate" else
                ("raw_binary" if operation == "audio_generate" else
                 "json_text" if operation in ("image_input", "audio_transcribe") else "json_base64"),
            media_types=("video/mp4",) if operation == "video_generate" else
                ("audio/mpeg",) if operation in ("audio_generate", "audio_transcribe") else ("image/png",),
            poll_path="/v1/jobs/{job_id}" if operation == "video_generate" else None,
            result_path="/v1/jobs/{job_id}/assets" if operation == "video_generate" else None,
            download_origins=("https://assets.example.org",) if operation == "video_generate" else (),
        )
    )


class FakeHTTP:
    def __init__(self, operation, response):
        self.operation = operation
        self.response = response
        self.requests = []
    def send(self, method, url, body, headers, limit):
        self.requests.append((method, url, body, headers, limit))
        return self.response, "application/json"


def service(tmp_path):
    store = EventStore(str(tmp_path / "runtime.db"))
    return RuntimeService(store)


def prepare(svc, operation, *, files=None):
    r = route(operation)
    registry = MediaRouteRegistry({r.adapter_id: r})
    intent = {"operation": operation, "provider": r.provider, "model": r.model,
              "adapterId": r.adapter_id, "providerNetworkPolicy": "remote_allowed",
              "maxCostUSD": 0.5, "prompt": "Generate media for safe testing.",
              "files": files or []}
    result = prepare_media_approval(svc, intent, metadata("prepare"), registry=registry)
    return registry, result


def approve(svc, result):
    meta = metadata("decide")
    svc.submit_human_approval_decision({
        "schemaVersion": "1.0.0", "requestId": result["requestId"],
        "decision": "approve", "operatorId": "operator-test",
        "decidedAt": meta["issuedAt"], "correlationId": meta["correlationId"],
        "idempotencyKey": meta["idempotencyKey"],
    }, meta)


def test_image_generation_requires_approval_and_dispatches_once(tmp_path):
    svc = service(tmp_path)
    registry, result = prepare(svc, "image_generate")
    http = FakeHTTP("image_generate", json.dumps({
        "data": [{"b64_json": base64.b64encode(b"\x89PNG\r\n\x1a\nimage-test-content").decode()}]
    }).encode())
    with pytest.raises(AuthorityViolation):
        submit_approved_media(
            svc, result["requestId"], metadata("submit"), registry=registry,
            transport=http, credential_resolver=lambda _: "test-credential"
        )
    assert not http.requests
    approve(svc, result)
    key = metadata("submit", "media-submit-fixed-identity-1234")
    completed = submit_approved_media(
        svc, result["requestId"], key, registry=registry,
        transport=http, credential_resolver=lambda _: "test-credential"
    )
    assert completed["state"] == "completed"
    assert len(http.requests) == 1
    assert http.requests[0][1] == "https://api.example.org/v1/media/image_generate"
    artifact = completed["artifactCandidate"]
    assert Path(artifact["artifactPath"]).read_bytes().endswith(b"image-test-content")
    assert artifact["trust"] == "untrusted"
    assert artifact["verificationState"] == "pending_human_verification"
    repeated = submit_approved_media(
        svc, result["requestId"], key, registry=registry,
        transport=http, credential_resolver=lambda _: "test-credential"
    )
    assert repeated["state"] == "completed"
    assert len(http.requests) == 1
    svc.store.close()


def test_video_submit_persists_operation_id_and_does_not_regenerate(tmp_path):
    svc = service(tmp_path)
    registry, result = prepare(svc, "video_generate")
    approve(svc, result)
    transport = FakeHTTP("video_generate", b'{"name":"operations/abc123"}')
    submitted = submit_approved_media(
        svc, result["requestId"], metadata("run"),
        registry=registry, transport=transport,
        credential_resolver=lambda _: "test",
    )
    assert submitted["state"] == "submitted"
    assert submitted["operationId"] == "operations/abc123"
    svc.store.close()

    reopened = EventStore(str(tmp_path / "runtime.db"))
    status = media_job_status(reopened, result["driverRunId"])
    assert status["operationId"] == "operations/abc123"
    assert status["safeToResubmit"] is False
    reopened.close()


def test_provider_failure_after_dispatch_is_indeterminate_not_replayed(tmp_path):
    svc = service(tmp_path)
    registry, result = prepare(svc, "image_generate")
    approve(svc, result)
    class FailingHTTP:
        count = 0
        def send(self, *args):
            self.count += 1
            raise TimeoutError("provider timeout after request accepted")
    transport = FailingHTTP()
    with pytest.raises(TimeoutError):
        submit_approved_media(svc, result["requestId"], metadata("run"),
                              registry=registry, transport=transport,
                              credential_resolver=lambda _: "test")
    assert transport.count == 1
    assert media_job_status(svc.store, result["driverRunId"])["state"] == "indeterminate"
    assert submit_approved_media(
        svc, result["requestId"], metadata("new-run-id"), registry=registry,
        transport=transport, credential_resolver=lambda _: "test")["state"] == "indeterminate"
    assert transport.count == 1
    svc.store.close()


def test_video_poll_and_download_preserve_single_generation(tmp_path):
    from capt_runtime.media_execution import poll_media_job, fetch_media_artifact
    svc = service(tmp_path)
    registry, approval = prepare(svc, "video_generate")
    approve(svc, approval)
    calls = []
    video = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 42

    class SequenceHTTP:
        def send(self, method, url, body, headers, limit):
            calls.append((method, url))
            if method == "POST":
                return b'{"name":"operations/abc123"}', "application/json"
            if method == "GET" and url.endswith("/operations/abc123"):
                if len([x for x in calls if x[1].endswith("/operations/abc123")]) == 1:
                    return b'{"done":false}', "application/json"
                return json.dumps({
                    "done": True,
                    "response": {"generateVideoResponse": {
                        "generatedSamples": [{"video": {
                            "uri": "https://assets.example.org/files/clip.mp4?token=private"
                        }}]
                    }}
                }).encode(), "application/json"
            if method == "GET" and url.startswith("https://assets.example.org/"):
                return video, "video/mp4"
            raise AssertionError("unexpected network call " + url)

    http = SequenceHTTP()
    result = submit_approved_media(
        svc, approval["requestId"], metadata("run"),
        registry=registry, transport=http, credential_resolver=lambda _: "test"
    )
    assert result["state"] == "submitted"
    result = poll_media_job(svc, approval["requestId"], registry=registry,
                            transport=http, credential_resolver=lambda _: "test")
    assert result["state"] == "processing"
    result = poll_media_job(svc, approval["requestId"], registry=registry,
                            transport=http, credential_resolver=lambda _: "test")
    assert result["state"] == "ready_to_download"
    assert "downloadUrl" not in result
    assert "private" not in str(result)
    result = fetch_media_artifact(svc, approval["requestId"], registry=registry,
                                  transport=http, credential_resolver=lambda _: "test")
    assert result["state"] == "completed"
    assert Path(result["artifactCandidate"]["artifactPath"]).read_bytes() == video
    same = fetch_media_artifact(svc, approval["requestId"], registry=registry,
                                transport=http, credential_resolver=lambda _: "test")
    assert same["state"] == "completed"
    assert sum(method == "POST" for method, _ in calls) == 1
    assert sum("assets.example.org" in url for _, url in calls) == 1
    svc.store.close()


def test_video_poll_rejects_untrusted_download_host_and_keeps_operation(tmp_path):
    from capt_runtime.media_execution import poll_media_job
    svc = service(tmp_path)
    registry, approval = prepare(svc, "video_generate")
    approve(svc, approval)
    class SSRFMock:
        def send(self, method, url, body, headers, limit):
            if method == "POST":
                return b'{"name":"operations/abc123"}', "application/json"
            return json.dumps({
                "done": True, "response": {"generateVideoResponse": {
                    "generatedSamples": [{"video": {"uri": "http://169.254.169.254/latest"}}]
                }}
            }).encode(), "application/json"
    http = SSRFMock()
    submit_approved_media(svc, approval["requestId"], metadata("run"), registry=registry,
                          transport=http, credential_resolver=lambda _: "test")
    with pytest.raises(AuthorityViolation, match="DOWNLOAD_HOST"):
        poll_media_job(svc, approval["requestId"], registry=registry,
                       transport=http, credential_resolver=lambda _: "test")
    status = media_job_status(svc.store, approval["driverRunId"])
    assert status["state"] == "submitted"
    assert status["operationId"] == "operations/abc123"
    svc.store.close()


def test_authenticated_operator_commands_and_read_only_catalog(tmp_path):
    from desktop.m1_command_service import RuntimeCommandService
    from desktop.capt_runtime_service import RuntimeQueryService

    svc = service(tmp_path)
    registry, _ = prepare(svc, "image_generate")
    # An empty registry must never advertise media capabilities.
    assert RuntimeQueryService(svc.store).handle({"op": "media_route_catalog"})["result"] == []

    fake = FakeHTTP("image_generate", json.dumps({"data": [{"b64_json":
        base64.b64encode(b"\x89PNG\r\n\x1a\ntest").decode()}]}).encode())
    relay = RuntimeCommandService(
        svc.store, "operator-test", "sess-media",
        runtime_service=svc, media_registry=registry, media_transport=fake,
        media_credential_resolver=lambda _: "test"
    )
    def cmd(op, payload):
        return {
            "schemaVersion":"1.0.0", "op":op, "payload":payload,
            "commandId":"cmd-"+uuid.uuid4().hex,
            "operatorId":"operator-test", "sessionId":"sess-media",
            "idempotencyKey":"idem-"+uuid.uuid4().hex,
            "correlationId":"corr-"+uuid.uuid4().hex,
            "timestamp":datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        }
    route_row = route("image_generate")
    prep = relay.execute(cmd("prepare_media_approval", {
        "operation":"image_generate", "provider":route_row.provider,
        "model":route_row.model, "adapterId":route_row.adapter_id,
        "providerNetworkPolicy":"remote_allowed", "maxCostUSD":0.6,
        "prompt":"An abstract test image", "files":[]
    }))
    assert prep["status"] == "accepted", prep
    request_id = prep["result"]["requestId"]
    denied = relay.execute(cmd("submit_approved_media", {"requestId":request_id}))
    assert denied["status"] == "rejected"
    assert not fake.requests
    decision = relay.execute(cmd("submit_approval_decision", {
        "requestId": request_id, "decision":"approve",
    }))
    assert decision["status"] == "accepted"
    result = relay.execute(cmd("submit_approved_media", {"requestId":request_id}))
    assert result["status"] == "accepted", result
    assert result["result"]["state"] == "completed"
    query = RuntimeQueryService(svc.store, media_registry=registry).handle({
        "op":"media_job_status", "driverRunId":prep["result"]["driverRunId"]
    })
    assert query["result"]["state"] == "completed"
    assert len(fake.requests) == 1
    svc.store.close()


def test_image_bytes_reach_approved_vision_endpoint_not_merely_filename(tmp_path):
    svc = service(tmp_path)
    image = b"\x89PNG\r\n\x1a\n" + b"local-vision-asset"
    session = tmp_path / "native-media-intake" / "v1" / str(uuid.uuid4())
    session.mkdir(parents=True)
    name = str(uuid.uuid4()) + "-image.png"
    source = session / name
    source.write_bytes(image)
    import hashlib
    item = {
        "stagedPath": str(source),
        "sha256": "sha256:" + hashlib.sha256(image).hexdigest(),
        "sizeBytes": len(image), "mediaType": "image/png", "originalName":"image.png"
    }
    registry, approval = prepare(svc, "image_input", files=[item])
    approve(svc, approval)
    http = FakeHTTP("image_input", b'{"choices":[{"message":{"content":"A square"}}]}')
    result = submit_approved_media(svc, approval["requestId"], metadata("run"),
        registry=registry, transport=http, credential_resolver=lambda _: "test")
    assert result["state"] == "completed"
    assert result["resultText"] == "A square"
    posted = json.loads(http.requests[0][2])
    content = posted["messages"][0]["content"]
    assert content[0]["text"] == "Generate media for safe testing."
    assert len(content) == 2
    url = content[1]["image_url"]["url"]
    assert url.startswith("data:image/png;base64,")
    assert base64.b64decode(url.split(",", 1)[1]) == image
    assert str(source) not in str(posted)
    svc.store.close()


def test_invalid_mime_signature_blocks_before_approval_and_network(tmp_path):
    svc = service(tmp_path)
    folder = tmp_path / "native-media-intake" / "v1" / str(uuid.uuid4())
    folder.mkdir(parents=True)
    path = folder / (str(uuid.uuid4()) + "-fake.png")
    payload = b"<script>not a png</script>"
    path.write_bytes(payload)
    import hashlib
    item = {"stagedPath": str(path),
            "sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
            "sizeBytes": len(payload), "mediaType": "image/png"}
    with pytest.raises(AuthorityViolation, match="SIGNATURE"):
        prepare(svc, "image_input", files=[item])
    assert svc.store.head_sequence() == 0
    svc.store.close()


def test_audio_generation_creates_local_unverified_playable_candidate(tmp_path):
    svc = service(tmp_path)
    registry, approval = prepare(svc, "audio_generate")
    approve(svc, approval)
    http = FakeHTTP("audio_generate", b"ID3" + b"mock-mp3-content")
    output = submit_approved_media(svc, approval["requestId"], metadata("run"),
        registry=registry, transport=http, credential_resolver=lambda _: "test")
    assert output["state"] == "completed"
    candidate = output["artifactCandidate"]
    assert candidate["mediaType"] == "audio/mpeg"
    assert Path(candidate["artifactPath"]).suffix == ".mp3"
    assert Path(candidate["artifactPath"]).read_bytes() == b"ID3mock-mp3-content"
    assert len(http.requests) == 1
    svc.store.close()


def test_changed_adapter_contract_after_approval_is_refused_before_dispatch(tmp_path):
    from dataclasses import replace
    svc = service(tmp_path)
    original, approved = prepare(svc, "image_generate")
    approve(svc, approved)
    old = original.routes["mock-image_generate"]
    changed = MediaRouteRegistry({
        old.adapter_id: replace(old, contract=replace(
            old.contract, submit_path="/v1/redirected-image-endpoint"
        ))
    })
    transport = FakeHTTP("image_generate", b'{"data":[]}')
    with pytest.raises(AuthorityViolation, match="ROUTE_CHANGED"):
        submit_approved_media(svc, approved["requestId"], metadata("submit"),
            registry=changed, transport=transport,
            credential_resolver=lambda _: "test")
    assert not transport.requests
    state = svc.store.require_state("human_approval-" + approved["requestId"])
    assert state["state"] == "approved"
    svc.store.close()


def test_audio_transcription_binds_real_multipart_input_bytes(tmp_path):
    svc = service(tmp_path)
    audio = b"ID3" + b"mock-waveform-content"
    folder = tmp_path / "native-media-intake" / "v1" / str(uuid.uuid4())
    folder.mkdir(parents=True)
    source = folder / (str(uuid.uuid4()) + "-speech.mp3")
    source.write_bytes(audio)
    import hashlib
    item = {"stagedPath":str(source),
            "sha256":"sha256:"+hashlib.sha256(audio).hexdigest(),
            "sizeBytes":len(audio),"mediaType":"audio/mpeg",
            "originalName":"speech.mp3"}
    registry, approved = prepare(svc, "audio_transcribe", files=[item])
    approve(svc, approved)
    fake = FakeHTTP("audio_transcribe", b'{"text":"mock spoken words"}')
    receipt = submit_approved_media(svc, approved["requestId"], metadata("run"),
        registry=registry, transport=fake, credential_resolver=lambda _: "test")
    assert receipt["state"] == "completed"
    assert receipt["resultText"] == "mock spoken words"
    method, url, body, headers, limit = fake.requests[0]
    assert headers["Content-Type"].startswith("multipart/form-data; boundary=")
    assert audio in body and b'mock-model' in body
    assert b"speech.mp3" not in body
    svc.store.close()


def test_production_video_download_streams_to_private_file(tmp_path):
    from capt_runtime.media_execution import _download_video_streaming
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading

    content = b"\x00\x00\x00\x18ftypisom" + (b"video-data" * 100_000)
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/generated.mp4"
        receipt = _download_video_streaming(
            url, {}, len(content) + 1,
            state_root=tmp_path, driver_run_id="dr-media-1234567890abcdef"
        )
        path = Path(receipt["artifactPath"])
        assert path.read_bytes() == content
        assert receipt["sizeBytes"] == len(content)
        assert receipt["mediaType"] == "video/mp4"
        assert not path.with_name("download.partial").exists()
        with pytest.raises(AuthorityViolation):
            _download_video_streaming(
                url, {}, 12, state_root=tmp_path,
                driver_run_id="dr-media-other1234567890"
            )
    finally:
        server.shutdown()
        server.server_close()
