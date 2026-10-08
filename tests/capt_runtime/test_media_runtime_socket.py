"""Exact authenticated runtime socket → HumanApproval → local media provider."""
from __future__ import annotations

import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time


def test_end_to_end_local_media_route_without_paid_requests(tmp_path):
    from desktop.capt_runtime_service import serve
    from desktop.desktop_runtime_client import RuntimeClient

    png = b"\x89PNG\r\n\x1a\n" + b"mock-image-content"
    requests = []

    class Server(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            requests.append((self.path, json.loads(body)))
            result = json.dumps({"data": [{"b64_json": base64.b64encode(png).decode()}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(result)))
            self.end_headers()
            self.wfile.write(result)

        def log_message(self, fmt, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Server)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    origin = f"http://127.0.0.1:{port}"

    ui = tmp_path / "ui"
    ui.mkdir()
    (ui / "providers.json").write_text(json.dumps({
        "providers": [{
            "id":"local-media-test", "enabled":True, "kind":"local",
            "capabilities":["image"], "transport":"openai_compatible",
            "base_url":origin+"/v1", "models":["test-image"]
        }]
    }))
    (ui / "media-routes.json").write_text(json.dumps({
        "schemaVersion":"1.0.0", "routes":[{
            "enabled":True, "adapterId":"local-images",
            "provider":"local-media-test", "model":"test-image",
            "operation":"image_generate", "origin":origin,
            "transport":"json", "submitPath":"/v1/images",
            "responseType":"json_base64", "mediaTypes":["image/png"],
            "maximumPriceUSD":0.0, "authStyle":"none"
        }]
    }))

    socket = str(tmp_path / "runtime.sock")
    token = str(tmp_path / "runtime.token")
    ledger = str(tmp_path / "runtime.db")
    runtime = threading.Thread(target=serve, args=(ledger, socket, token, False), daemon=True)
    runtime.start()
    for _ in range(200):
        if Path(socket).exists() and Path(token).exists():
            break
        time.sleep(.05)
    client = RuntimeClient(socket, token)
    client.connect()
    try:
        catalog = client._query({"op":"media_route_catalog"})
        assert catalog["ok"] is True
        assert catalog["result"][0]["adapterId"] == "local-images"
        proposal = client.command("prepare_media_approval", {
            "operation":"image_generate", "provider":"local-media-test",
            "model":"test-image", "adapterId":"local-images",
            "providerNetworkPolicy":"local_only", "maxCostUSD":0.0,
            "prompt":"Generate an offline PNG fixture", "files":[]
        }, idempotency_key="media-local-approval-once")
        assert proposal["status"] == "accepted", proposal
        request_id = proposal["result"]["requestId"]
        assert requests == []
        blocked = client.command("submit_approved_media",
            {"requestId": request_id}, idempotency_key="media-local-denied")
        assert blocked["status"] == "rejected"
        assert requests == []
        approved = client.command("submit_approval_decision",
            {"requestId":request_id,"decision":"approve"},
            idempotency_key="media-local-human-approve")
        assert approved["status"] == "accepted", approved
        completed = client.command("submit_approved_media",
            {"requestId":request_id}, idempotency_key="media-local-execute-once")
        assert completed["status"] == "accepted", completed
        receipt = completed["result"]
        assert receipt["state"] == "completed"
        assert Path(receipt["artifactCandidate"]["artifactPath"]).read_bytes() == png
        assert len(requests) == 1
        again = client.command("submit_approved_media",
            {"requestId":request_id}, idempotency_key="media-local-execute-once")
        assert again["result"]["state"] == "completed"
        assert len(requests) == 1
        before = client._query({"op":"identity"})["result"]["headSequence"]
        status = client._query({"op":"media_job_status",
                                "driverRunId":proposal["result"]["driverRunId"]})
        assert status["result"]["state"] == "completed"
        assert client._query({"op":"identity"})["result"]["headSequence"] == before
        assert "media_job_status" in client.capabilities()["queryOperations"]
    finally:
        client.disconnect()
        server.shutdown()
        server.server_close()


def test_invalid_optional_media_configuration_is_fail_closed_not_runtime_outage(tmp_path):
    from desktop.capt_runtime_service import serve
    from desktop.desktop_runtime_client import RuntimeClient

    ui = tmp_path / "ui"
    ui.mkdir()
    (ui / "media-routes.json").write_text('{"schemaVersion":"invalid","routes":[]}')
    sock = str(tmp_path / "invalid-media.sock")
    token = str(tmp_path / "invalid-media.token")
    worker = threading.Thread(
        target=serve,
        args=(str(tmp_path / "invalid-media.db"), sock, token, False),
        daemon=True,
    )
    worker.start()
    for _ in range(100):
        if Path(sock).exists() and Path(token).exists():
            break
        time.sleep(.05)
    client = RuntimeClient(sock, token)
    client.connect()
    try:
        assert client._query({"op": "identity"})["result"]["integrity"] == "ok"
        from desktop.desktop_runtime_client import RuntimeClientError
        import pytest
        with pytest.raises(RuntimeClientError, match="MEDIA_CONFIGURATION_INVALID"):
            client._query({"op": "media_route_catalog"})
        assert "prepare_media_approval" in client.capabilities()["commandOperations"]
    finally:
        client.disconnect()
