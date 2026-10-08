"""Authenticated local media end-to-end: PDF → approval → Gemini-typed bytes."""
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
import uuid


def test_native_document_route_reaches_mock_gemini_interactions(tmp_path):
    from desktop.capt_runtime_service import serve
    from desktop.desktop_runtime_client import RuntimeClient

    payload = b"%PDF-1.4\n1 0 obj\nendobj\n%%EOF"
    folder = tmp_path / "native-media-intake" / "v1" / str(uuid.uuid4())
    folder.mkdir(parents=True)
    file = folder / (str(uuid.uuid4()) + "-file.pdf")
    file.write_bytes(payload)
    requests = []

    class MockProvider(BaseHTTPRequestHandler):
        def do_POST(self):
            size = int(self.headers.get("Content-Length", "0"))
            doc = json.loads(self.rfile.read(size))
            requests.append((self.path, doc))
            body = json.dumps({"status": "completed", "outputs": [
                {"type": "text", "text": "PDF mock analyzed"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *args):
            pass

    provider = ThreadingHTTPServer(("127.0.0.1", 0), MockProvider)
    threading.Thread(target=provider.serve_forever, daemon=True).start()
    origin = "http://127.0.0.1:" + str(provider.server_address[1])
    ui = tmp_path / "ui"
    ui.mkdir()
    (ui / "providers.json").write_text(json.dumps({"providers": [{
        "id": "gemini-local", "enabled": True, "kind": "local",
        "capabilities": ["document"], "transport": "openai_compatible",
        "base_url": origin + "/v1beta", "models": ["fixture-document"]
    }]}))
    (ui / "media-routes.json").write_text(json.dumps({"schemaVersion": "1.0.0",
        "routes": [{
            "enabled": True, "adapterId": "fixture-gemini-document",
            "provider": "gemini-local", "model": "fixture-document",
            "operation": "document_input", "origin": origin,
            "transport": "gemini_interactions",
            "submitPath": "/v1beta/interactions",
            "responseType": "json_text", "mediaTypes": ["application/pdf"],
            "authStyle": "none", "maximumPriceUSD": 0
        }]}))

    sock = str(tmp_path / "runtime.sock")
    token = str(tmp_path / "runtime.token")
    ledger = str(tmp_path / "runtime.db")
    threading.Thread(target=serve, args=(ledger, sock, token, False), daemon=True).start()
    for _ in range(100):
        if Path(sock).exists() and Path(token).exists():
            break
        time.sleep(.05)
    client = RuntimeClient(sock, token)
    client.connect()
    try:
        catalog = client._query({"op": "media_route_catalog"})
        assert catalog["ok"] is True
        assert len(catalog["result"]) == 1
        approval = client.command("prepare_media_approval", {
            "operation": "document_input", "provider": "gemini-local",
            "model": "fixture-document", "adapterId": "fixture-gemini-document",
            "providerNetworkPolicy": "local_only",
            "maxCostUSD": 0, "prompt": "Summarize this PDF fixture",
            "files": [{"stagedPath": str(file), "originalName": "file.pdf",
                       "sizeBytes": len(payload), "mediaType": "application/pdf",
                       "sha256": "sha256:" + hashlib.sha256(payload).hexdigest()}]
        }, idempotency_key="r2b-fixture-prepare")
        assert approval["status"] == "accepted", approval
        assert not requests
        ref = approval["result"]["requestId"]
        result = client.command("submit_approved_media", {"requestId": ref},
                                idempotency_key="r2b-fixture-blocked")
        assert result["status"] == "rejected", result
        assert not requests
        decided = client.command("submit_approval_decision",
                                 {"requestId": ref, "decision": "approve"},
                                 idempotency_key="r2b-fixture-approval")
        assert decided["status"] == "accepted", decided
        result = client.command("submit_approved_media", {"requestId": ref},
                                idempotency_key="r2b-fixture-submit")
        assert result["status"] == "accepted", result
        assert result["result"]["state"] == "completed"
        assert result["result"]["resultText"] == "PDF mock analyzed"
        assert len(requests) == 1
        assert requests[0][0] == "/v1beta/interactions"
        input_file = requests[0][1]["input"][1]
        assert input_file["type"] == "document"
        assert base64.b64decode(input_file["data"]) == payload
        again = client.command("submit_approved_media", {"requestId": ref},
                               idempotency_key="r2b-fixture-duplicate")
        assert again["result"]["state"] == "completed"
        assert len(requests) == 1
    finally:
        client.disconnect()
        provider.shutdown()
