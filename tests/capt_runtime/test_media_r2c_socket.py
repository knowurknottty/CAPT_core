"""Live RuntimeService Unix-socket integration, mock local Gemini HTTP.

No paid calls, no external hosts, no provider secrets persisted.
"""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
import uuid


def test_gemini_files_two_human_approvals_over_live_socket(tmp_path, monkeypatch):
    from desktop.capt_runtime_service import serve
    from desktop.desktop_runtime_client import RuntimeClient

    pdf = b"%PDF-1.4\n" + bytes(13 * 1024 * 1024)
    staged = tmp_path / "native-media-intake" / "v1" / str(uuid.uuid4())
    staged.mkdir(parents=True)
    source = staged / (str(uuid.uuid4()) + "-manual.pdf")
    source.write_bytes(pdf)
    seen = {"start": 0, "upload": 0, "model": 0, "status": 0}

    server = None
    class Provider(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            if self.path == "/upload/v1beta/files":
                seen["start"] += 1
                assert self.headers["x-goog-api-key"] == "fixture-only"
                self.send_response(200)
                self.send_header("X-Goog-Upload-URL",
                    "http://127.0.0.1:" + str(server.server_address[1]) +
                    "/upload/v1beta/files?upload_id=fixture")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if self.path.startswith("/upload/v1beta/files?"):
                seen["upload"] += 1
                assert body == pdf
                answer = {"file": {"name": "files/socket_fixture123",
                    "uri": "http://127.0.0.1:" + str(server.server_address[1]) +
                           "/v1beta/files/socket_fixture123",
                    "mimeType": "application/pdf", "state": "PROCESSING"}}
            else:
                assert self.path == "/v1beta/interactions"
                seen["model"] += 1
                data = json.loads(body)
                assert data["input"][1]["type"] == "document"
                assert "uri" in data["input"][1] and "data" not in data["input"][1]
                answer = {"status": "completed", "outputs": [
                    {"type": "text", "text": "Mock model analyzed approved file"}]}
            encoded = json.dumps(answer).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            assert self.path == "/v1beta/files/socket_fixture123"
            seen["status"] += 1
            encoded = json.dumps({"file": {
                "name": "files/socket_fixture123",
                "uri": "http://127.0.0.1:" + str(server.server_address[1]) +
                       "/v1beta/files/socket_fixture123",
                "mimeType": "application/pdf", "state": "ACTIVE"
            }}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = "http://127.0.0.1:" + str(server.server_address[1])
    ui = tmp_path / "ui"
    ui.mkdir()
    provider = {"id": "gemini_fixture", "enabled": True, "kind": "local",
                "transport": "gemini_interactions",
                "base_url": origin + "/v1beta", "models": ["fixture-model"],
                "capabilities": ["file_upload", "file_reference"]}
    (ui / "providers.json").write_text(json.dumps({"providers": [provider]}))
    routes = []
    for operation, path, transport, response in [
        ("file_upload", "/upload/v1beta/files", "gemini_resumable", "file_receipt"),
        ("file_reference_input", "/v1beta/interactions", "gemini_interactions", "json_text"),
    ]:
        routes.append({
            "enabled": True, "adapterId": "fixture-" + operation,
            "provider": "gemini_fixture", "model": "fixture-model",
            "operation": operation, "origin": origin, "transport": transport,
            "submitPath": path, "responseType": response,
            "mediaTypes": ["application/pdf"], "authStyle": "x-goog-api-key",
            "maximumPriceUSD": 0
        })
    (ui / "media-routes.json").write_text(json.dumps({
        "schemaVersion": "1.0.0", "routes": routes
    }))
    monkeypatch.setenv("CAPT_PROVIDER_KEY_GEMINI_FIXTURE", "fixture-only")

    ledger = str(tmp_path / "runtime.db")
    sock = str(tmp_path / "runtime.sock")
    token = str(tmp_path / "runtime.token")
    threading.Thread(target=serve, args=(ledger, sock, token, False), daemon=True).start()
    for _ in range(100):
        if Path(sock).exists() and Path(token).exists():
            break
        time.sleep(.05)
    client = RuntimeClient(sock, token)
    client.connect()

    def command(op, data, name):
        return client.command(op, data, idempotency_key="r2c-" + name)

    def approve(ref, name):
        response = command("submit_approval_decision", {
            "requestId": ref, "decision": "approve"
        }, "approve-" + name)
        assert response["status"] == "accepted", response

    try:
        catalog = client._query({"op": "media_route_catalog"})
        assert catalog["ok"] and len(catalog["result"]) == 2
        upload = command("prepare_media_approval", {
            "adapterId": "fixture-file_upload",
            "operation": "file_upload", "provider": "gemini_fixture",
            "model": "fixture-model",
            "providerNetworkPolicy": "local_only", "maxCostUSD": 0,
            "prompt": "Make this available for later separate consent",
            "files": [{
                "stagedPath": str(source), "sha256": "sha256:" + hashlib.sha256(pdf).hexdigest(),
                "sizeBytes": len(pdf), "mediaType": "application/pdf",
                "originalName": "manual.pdf"
            }]
        }, "prepare-upload")
        assert upload["status"] == "accepted", upload
        ref = upload["result"]["requestId"]
        driver = upload["result"]["driverRunId"]
        denied = command("submit_approved_media", {"requestId": ref}, "unapproved")
        assert denied["status"] == "rejected"
        assert seen == {"start": 0, "upload": 0, "model": 0, "status": 0}
        approve(ref, "upload")
        outcome = command("submit_approved_media", {"requestId": ref}, "execute-upload")
        assert outcome["status"] == "accepted", outcome
        assert outcome["result"]["state"] == "file_processing"
        assert seen["start"] == 1 and seen["upload"] == 1
        status = command("poll_media_job", {"requestId": ref}, "poll-upload")
        assert status["status"] == "accepted", status
        assert status["result"]["state"] == "file_active"
        assert seen["status"] == 1 and seen["model"] == 0

        model = command("prepare_media_approval", {
            "adapterId": "fixture-file_reference_input",
            "operation": "file_reference_input", "provider": "gemini_fixture",
            "model": "fixture-model",
            "providerNetworkPolicy": "local_only", "maxCostUSD": 0,
            "prompt": "Explain the approved uploaded document.",
            "uploadedDriverRunId": driver, "files": []
        }, "prepare-reference")
        assert model["status"] == "accepted", model
        ref2 = model["result"]["requestId"]
        denied2 = command("submit_approved_media", {"requestId": ref2}, "unapproved-model")
        assert denied2["status"] == "rejected"
        assert seen["model"] == 0
        approve(ref2, "reference")
        result = command("submit_approved_media", {"requestId": ref2}, "execute-reference")
        assert result["status"] == "accepted", result
        assert result["result"]["state"] == "completed"
        assert result["result"]["resultText"] == "Mock model analyzed approved file"
        assert seen == {"start": 1, "upload": 1, "model": 1, "status": 1}
        duplicate = command("submit_approved_media", {"requestId": ref2}, "duplicate")
        assert duplicate["result"]["state"] == "completed"
        assert seen["model"] == 1
    finally:
        client.disconnect()
        server.shutdown()
