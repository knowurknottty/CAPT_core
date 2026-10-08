"""No-cost Gemini Files API: governed upload and independent file-reference approval."""
import hashlib
import json
from pathlib import Path
import uuid

import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.media_adapter_contract import MediaAdapterContract
from capt_runtime.media_execution import (
    MediaRoute, MediaRouteRegistry, prepare_media_approval, submit_approved_media,
    poll_media_job, media_job_status,
)
from tests.capt_runtime.test_media_execution import service, metadata, approve, FakeHTTP


ORIGIN = "https://generativelanguage.googleapis.com"
FILE_NAME = "files/fixture_ABC123xyz"
FILE_URI = ORIGIN + "/v1beta/" + FILE_NAME


def route(operation):
    return MediaRoute(
        adapter_id="gemini-" + operation, provider="gemini-fixture",
        model="gemini-3.8-flash", maximum_price_usd=0,
        auth_style="x-goog-api-key",
        contract=MediaAdapterContract(
            provider_id="gemini-fixture", origin=ORIGIN,
            operation=operation,
            transport=("gemini_resumable" if operation == "file_upload"
                       else "gemini_interactions"),
            submit_path=("/upload/v1beta/files" if operation == "file_upload"
                         else "/v1beta/interactions"),
            response_type=("file_receipt" if operation == "file_upload" else "json_text"),
            media_types=("application/pdf",),
            max_asset_bytes=2 * 1024 * 1024 * 1024,
        )
    )


def uploaded_file(folder, *, size=13 * 1024 * 1024):
    destination = folder / "native-media-intake" / "v1" / str(uuid.uuid4())
    destination.mkdir(parents=True)
    target = destination / (str(uuid.uuid4()) + "-manual.pdf")
    with target.open("wb") as handle:
        handle.write(b"%PDF-1.5\n")
        handle.truncate(size)
    h = hashlib.sha256()
    with target.open("rb") as file:
        while chunk := file.read(1_048_576):
            h.update(chunk)
    return {"stagedPath": str(target), "sizeBytes": size,
            "sha256": "sha256:" + h.hexdigest(),
            "originalName": "manual.pdf", "mediaType": "application/pdf"}


def approval(svc, route_, files, **other):
    registry = MediaRouteRegistry({route_.adapter_id: route_})
    request = prepare_media_approval(
        svc, {
            "operation": route_.contract.operation,
            "provider": route_.provider, "model": route_.model,
            "adapterId": route_.adapter_id,
            "providerNetworkPolicy": "remote_allowed",
            "maxCostUSD": 0,
            "prompt": "Describe this document.",
            "files": files, **other,
        }, metadata("prepare"), registry=registry)
    return registry, request


class FakeUploader:
    def __init__(self):
        self.starts = 0
        self.finalizes = 0
        self.polls = 0
        self.fail_finalize = False
        self.state = "PROCESSING"

    def start(self, *, origin, path, credential, mime, size, original_name):
        assert origin == ORIGIN and path == "/upload/v1beta/files"
        assert credential == "fixture-key" and mime == "application/pdf"
        assert size > 12 * 1024 * 1024
        self.starts += 1
        return ORIGIN + "/upload/v1beta/files?upload_id=opaque"

    def upload_and_finalize(self, *, session_url, origin, source, mime, size):
        assert session_url.startswith(ORIGIN + "/upload/")
        assert source.stat().st_size == size
        assert source.open("rb").read(5) == b"%PDF-"
        self.finalizes += 1
        if self.fail_finalize:
            raise TimeoutError("upload finalized but response lost")
        return self._response()

    def file_status(self, *, origin, file_name, credential):
        assert origin == ORIGIN and file_name == FILE_NAME
        assert credential == "fixture-key"
        self.polls += 1
        self.state = "ACTIVE"
        return self._response()

    def _response(self):
        return json.dumps({"file": {
            "name": FILE_NAME, "uri": FILE_URI,
            "mimeType": "application/pdf", "state": self.state
        }}).encode()


def test_large_file_upload_then_second_approval_consumes_uri_once(tmp_path):
    svc = service(tmp_path)
    item = uploaded_file(tmp_path)
    upload_route = route("file_upload")
    reg, pending = approval(svc, upload_route, [item])
    uploader = FakeUploader()
    with pytest.raises(AuthorityViolation):
        submit_approved_media(
            svc, pending["requestId"], metadata("unapproved"), registry=reg,
            transport=FakeHTTP("", b""),
            credential_resolver=lambda _: "fixture-key",
            upload_transport=uploader
        )
    assert uploader.starts == 0
    approve(svc, pending)
    upload_result = submit_approved_media(
        svc, pending["requestId"], metadata("upload"), registry=reg,
        transport=FakeHTTP("", b""), credential_resolver=lambda _: "fixture-key",
        upload_transport=uploader
    )
    assert upload_result["state"] == "file_processing"
    assert upload_result["safeToResubmit"] is False
    assert uploader.starts == 1 and uploader.finalizes == 1
    assert FILE_URI not in str(upload_result), "Provider URI is sealed in ledger"

    reopened = media_job_status(svc.store, pending["driverRunId"])
    assert reopened["state"] == "file_processing"
    refreshed = poll_media_job(
        svc, pending["requestId"], registry=reg,
        transport=FakeHTTP("", b""),
        credential_resolver=lambda _: "fixture-key", upload_transport=uploader
    )
    assert refreshed["state"] == "file_active"
    assert uploader.polls == 1
    again = submit_approved_media(
        svc, pending["requestId"], metadata("repeated-upload"), registry=reg,
        transport=FakeHTTP("", b""), credential_resolver=lambda _: "fixture-key",
        upload_transport=uploader)
    assert again["state"] == "file_active"
    assert uploader.starts == 1

    consume_route = route("file_reference_input")
    ref_reg, bound = approval(
        svc, consume_route, [], uploadedDriverRunId=pending["driverRunId"]
    )
    posted = FakeHTTP("file_reference_input",
        b'{"status":"completed","outputs":[{"type":"text","text":"Document analyzed"}]}')
    with pytest.raises(AuthorityViolation):
        submit_approved_media(svc, bound["requestId"], metadata("before-consent"),
                              registry=ref_reg, transport=posted,
                              credential_resolver=lambda _: "fixture-key")
    assert posted.requests == []
    approve(svc, bound)
    result = submit_approved_media(
        svc, bound["requestId"], metadata("read-file"), registry=ref_reg,
        transport=posted, credential_resolver=lambda _: "fixture-key"
    )
    assert result["state"] == "completed"
    assert result["resultText"] == "Document analyzed"
    assert len(posted.requests) == 1
    wire = json.loads(posted.requests[0][2])
    assert wire["input"][1] == {
        "type": "document", "uri": FILE_URI, "mime_type": "application/pdf"
    }
    assert "data" not in wire["input"][1]
    repeat = submit_approved_media(
        svc, bound["requestId"], metadata("read-again"), registry=ref_reg,
        transport=posted, credential_resolver=lambda _: "fixture-key"
    )
    assert repeat["state"] == "completed" and len(posted.requests) == 1
    svc.store.close()


def test_upload_lost_response_is_indeterminate_not_retried(tmp_path):
    svc = service(tmp_path)
    up = route("file_upload")
    reg, pending = approval(svc, up, [uploaded_file(tmp_path)])
    approve(svc, pending)
    uploader = FakeUploader()
    uploader.fail_finalize = True
    with pytest.raises(TimeoutError):
        submit_approved_media(svc, pending["requestId"], metadata("upload"),
                              registry=reg, transport=FakeHTTP("", b""),
                              credential_resolver=lambda _: "fixture-key",
                              upload_transport=uploader)
    assert media_job_status(svc.store, pending["driverRunId"])["state"] == "indeterminate"
    again = submit_approved_media(
        svc, pending["requestId"], metadata("retry"), registry=reg,
        transport=FakeHTTP("", b""), credential_resolver=lambda _: "fixture-key",
        upload_transport=uploader
    )
    assert again["state"] == "indeterminate"
    assert uploader.starts == 1 and uploader.finalizes == 1
    svc.store.close()


def test_reference_only_from_active_same_provider_file(tmp_path):
    svc = service(tmp_path)
    up = route("file_upload")
    reg, pending = approval(svc, up, [uploaded_file(tmp_path)])
    approve(svc, pending)
    fake = FakeUploader()
    submit_approved_media(svc, pending["requestId"], metadata("upload"),
                          registry=reg, transport=FakeHTTP("", b""),
                          credential_resolver=lambda _: "fixture-key",
                          upload_transport=fake)
    ref = route("file_reference_input")
    with pytest.raises(AuthorityViolation, match="NOT_ACTIVE"):
        approval(svc, ref, [], uploadedDriverRunId=pending["driverRunId"])
    with pytest.raises(AuthorityViolation, match="REFERENCE_ID_INVALID"):
        approval(svc, ref, [], uploadedDriverRunId="../../../secrets")
    svc.store.close()
