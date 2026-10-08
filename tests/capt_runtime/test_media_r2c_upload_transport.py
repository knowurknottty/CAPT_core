"""End-to-end HTTP transport with bounded streaming and no external network."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading

import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.media_file_upload import (
    GeminiResumableUploadTransport, validate_file_receipt, _validated_upload_url
)


def test_real_resumable_http_transport_streams_large_file_and_checks_session_url(tmp_path):
    blob_size = 15 * 1024 * 1024 + 31
    source = tmp_path / "fixture.pdf"
    with source.open("wb") as file:
        file.write(b"%PDF-1.5\n")
        file.truncate(blob_size)

    state = {"started": 0, "finalized": 0, "length": 0, "first": b""}
    server = None
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path == "/upload/v1beta/files":
                body = self.rfile.read(int(self.headers["Content-Length"]))
                assert json.loads(body)["file"]["display_name"] == "fixture.pdf"
                assert self.headers["X-Goog-Upload-Protocol"] == "resumable"
                assert self.headers["X-Goog-Upload-Command"] == "start"
                assert self.headers["x-goog-api-key"] == "mock-only"
                state["started"] += 1
                self.send_response(200)
                self.send_header(
                    "X-Goog-Upload-URL",
                    "http://127.0.0.1:" + str(server.server_address[1]) +
                    "/upload/v1beta/files?upload_id=opaque")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            assert self.path == "/upload/v1beta/files?upload_id=opaque"
            assert self.headers["X-Goog-Upload-Offset"] == "0"
            assert self.headers["X-Goog-Upload-Command"] == "upload, finalize"
            assert self.headers.get("x-goog-api-key") is None
            remain = int(self.headers["Content-Length"])
            assert remain == blob_size
            while remain:
                piece = self.rfile.read(min(1_048_576, remain))
                assert piece
                if not state["first"]:
                    state["first"] = piece[:5]
                remain -= len(piece)
                state["length"] += len(piece)
            state["finalized"] += 1
            body = json.dumps({"file": {
                "name": "files/transport123456",
                "uri": "http://127.0.0.1:" + str(server.server_address[1]) +
                       "/v1beta/files/transport123456",
                "state": "ACTIVE", "mimeType": "application/pdf",
            }}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = "http://127.0.0.1:" + str(server.server_address[1])
    try:
        uploader = GeminiResumableUploadTransport()
        url = uploader.start(
            origin=origin, path="/upload/v1beta/files",
            credential="mock-only", mime="application/pdf",
            size=blob_size, original_name="fixture.pdf"
        )
        response = uploader.upload_and_finalize(
            session_url=url, origin=origin, source=source,
            mime="application/pdf", size=blob_size
        )
        outcome = validate_file_receipt(response, mime="application/pdf", origin=origin)
        assert outcome["state"] == "file_active"
        assert state == {
            "started": 1, "finalized": 1,
            "length": blob_size, "first": b"%PDF-"
        }
    finally:
        server.shutdown()


@pytest.mark.parametrize("url", [
    "https://untrusted.example.com/upload/v1beta/files?upload_id=opaque",
    "file:///etc/passwd", "http://127.0.0.1:9001/upload/v1beta/files",
    "https://evil.com@api.example.org/upload/file",
    "https://api.example.org/v1beta/files/x"
])
def test_dynamic_upload_session_url_cannot_switch_authority(url):
    with pytest.raises(AuthorityViolation, match="MEDIA_UPLOAD_SESSION_ORIGIN_REFUSED"):
        _validated_upload_url(url, "https://api.example.org")


def test_unknown_file_id_or_unapproved_file_uri_refused():
    bad = json.dumps({"file": {
        "name": "files/abcdef0123456",
        "uri": "http://169.254.169.254/latest",
        "state": "ACTIVE", "mimeType": "application/pdf"
    }}).encode()
    with pytest.raises(AuthorityViolation, match="URI_ORIGIN_REFUSED"):
        validate_file_receipt(bad, mime="application/pdf", origin="https://api.example.org")
