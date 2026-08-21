from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from capt_runtime.drivers.provider import ProviderDriver, ProviderDriverFailure


class _Server(BaseHTTPRequestHandler):
    seen = {}

    def do_POST(self):  # noqa: N802
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        self.__class__.seen = {
            "path": self.path,
            "body": json.loads(raw),
            "auth": self.headers.get("Authorization"),
        }
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        payload = (
            {"response": "CAPT TEST"}
            if self.path.endswith("/api/generate")
            else {"choices": [{"message": {"content": "CAPT TEST"}}]}
        )
        self.wfile.write(json.dumps(payload).encode())

    def log_message(self, format, *args):  # noqa: N802,A002
        return


def _resolver():
    class Resolver:
        def resolve_for_execution(self, **_):
            return type("Task", (), {"objective": "minimal prompt"})()

    return Resolver()


def test_openrouter_driver_provenance_and_secret_not_persisted(tmp_path: Path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Server)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        secret = "synthetic-secret-not-to-persist"
        driver = ProviderDriver(
            str(tmp_path),
            provider_id="openrouter",
            model="deepseek/deepseek-v4-flash-0731",
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            api_key=secret,
            task_resolver=_resolver(),
        )
        out = asyncio.run(
            driver.submit(
                {
                    "driverRunId": "dr-1",
                    "missionId": "m-1",
                    "taskId": "t-1",
                    "contextSlice": {},
                    "submittedAt": "2026-01-01T00:00:00Z",
                }
            )
        )
        assert _Server.seen["path"] == "/v1/chat/completions"
        assert _Server.seen["body"]["model"] == "deepseek/deepseek-v4-flash-0731"
        assert _Server.seen["body"]["max_tokens"] == 16_384
        assert _Server.seen["auth"] == "Bearer " + secret
        assert out["state"] == "completed"
        assert out["dispatchBoundary"] == "response_completed"
        assert out["transportCancellationSupported"] is False
        assert out["diagnostics"]["provider"] == "openrouter"
        assert out["diagnostics"]["promptDigest"].startswith("sha256:")
        assert out["diagnostics"]["responseDigest"].startswith("sha256:")
        assert secret not in str(out)
        assert secret not in Path(out["artifactCandidate"]["artifactPath"]).read_text()
        inspected = asyncio.run(driver.inspect("dr-1"))
        assert inspected["state"] == "completed"
        assert inspected["dispatchBoundary"] == "response_completed"
        reconciled = asyncio.run(driver.reconcile("dr-1"))
        assert reconciled["result"] == "response_completed"
    finally:
        server.shutdown()
        server.server_close()


def test_ollama_driver_uses_native_generate_endpoint(tmp_path: Path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Server)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        driver = ProviderDriver(
            str(tmp_path),
            provider_id="ollama",
            model="local-model",
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            task_resolver=_resolver(),
        )
        out = asyncio.run(
            driver.submit(
                {
                    "driverRunId": "dr-2",
                    "missionId": "m-1",
                    "taskId": "t-1",
                    "contextSlice": {},
                    "submittedAt": "2026-01-01T00:00:00Z",
                }
            )
        )
        assert _Server.seen["path"] == "/api/generate"
        assert _Server.seen["body"] == {
            "model": "local-model",
            "prompt": "minimal prompt",
            "stream": False,
            "options": {"num_predict": 16_384},
        }
        assert _Server.seen["auth"] is None
        assert out["state"] == "completed"
        assert out["diagnostics"]["endpointClass"] == "local"
    finally:
        server.shutdown()
        server.server_close()


def test_cancel_is_truthful_request_not_false_transport_abort(tmp_path: Path):
    driver = ProviderDriver(
        str(tmp_path),
        provider_id="ollama",
        model="local-model",
        base_url="http://127.0.0.1:1/v1",
        task_resolver=_resolver(),
    )
    driver.runs["dr-cancel"] = {
        "state": "running",
        "cancelRequested": False,
        "dispatchBoundary": "request_started",
    }
    receipt = asyncio.run(driver.cancel("dr-cancel", "operator requested"))
    assert receipt == {
        "driverRunId": "dr-cancel",
        "state": "cancel_requested",
        "transportCancellationSupported": False,
    }
    inspected = asyncio.run(driver.inspect("dr-cancel"))
    assert inspected["cancelRequested"] is True
    assert inspected["state"] == "cancel_requested"
    reconciled = asyncio.run(driver.reconcile("dr-cancel"))
    assert reconciled["result"] == "external_state_unknown"


def test_cancel_rejects_unknown_run(tmp_path: Path):
    driver = ProviderDriver(
        str(tmp_path),
        provider_id="ollama",
        model="local-model",
        base_url="http://127.0.0.1:1/v1",
    )
    try:
        asyncio.run(driver.cancel("missing", "operator requested"))
    except ProviderDriverFailure as exc:
        assert "unknown driverRunId" in str(exc)
    else:
        raise AssertionError("unknown cancellation must fail")


def test_governed_provider_uses_explicit_approved_dispatch_prompt(tmp_path: Path):
    from capt_runtime.approval_dispatch import register_expected_prompt_digest
    import hashlib

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Server)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        approved = "approved-dispatch\n" + ("context evidence " * 60)
        digest = "sha256:" + hashlib.sha256(approved.encode()).hexdigest()
        register_expected_prompt_digest("dr-bound-long", digest)
        driver = ProviderDriver(
            str(tmp_path), provider_id="ollama", model="local-model",
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            task_resolver=_resolver(), dispatch_prompt=approved,
        )
        out = asyncio.run(driver.submit({
            "driverRunId": "dr-bound-long", "missionId": "m-1",
            "taskId": "t-1", "contextSlice": {},
            "submittedAt": "2026-01-01T00:00:00Z",
        }))
        assert len(approved) > 512
        assert _Server.seen["body"]["prompt"] == approved
        assert out["diagnostics"]["promptDigest"] == digest
    finally:
        server.shutdown()
        server.server_close()


def test_governed_provider_explicit_prompt_still_fails_closed_on_digest_mismatch(tmp_path: Path):
    from capt_runtime.approval_dispatch import register_expected_prompt_digest
    import hashlib

    approved = "approved prompt"
    expected = "different approved prompt"
    register_expected_prompt_digest(
        "dr-bound-mismatch", "sha256:" + hashlib.sha256(expected.encode()).hexdigest()
    )
    driver = ProviderDriver(
        str(tmp_path), provider_id="ollama", model="local-model",
        base_url="http://127.0.0.1:1/v1", task_resolver=_resolver(),
        dispatch_prompt=approved,
    )
    with __import__("pytest").raises(Exception, match="DISPATCH_DIGEST_MISMATCH"):
        asyncio.run(driver.submit({
            "driverRunId": "dr-bound-mismatch", "missionId": "m-1",
            "taskId": "t-1", "contextSlice": {},
            "submittedAt": "2026-01-01T00:00:00Z",
        }))


def test_openai_compatible_loopback_driver_reports_local_endpoint(tmp_path: Path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Server)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        driver = ProviderDriver(
            str(tmp_path),
            provider_id="mtplx",
            model="qwen3.8-27b-mtplx",
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            task_resolver=_resolver(),
        )
        out = asyncio.run(driver.submit({
            "driverRunId": "dr-local-openai",
            "missionId": "m-local",
            "taskId": "t-local",
            "contextSlice": {},
            "submittedAt": "2026-08-18T00:00:00Z",
        }))
        assert _Server.seen["path"] == "/v1/chat/completions"
        assert _Server.seen["auth"] is None
        assert out["diagnostics"]["endpointClass"] == "local"
        assert "EndpointClass: local" in Path(out["artifactCandidate"]["artifactPath"]).read_text()
    finally:
        server.shutdown()
        server.server_close()
