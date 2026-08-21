from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from capt_ui.operator.contract import ProviderKind
from capt_ui.operator.providers import Provider, ProviderManager


class _WarmServer(BaseHTTPRequestHandler):
    seen = {}

    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"data": [{"id": "qwen3.8-27b-mtplx"}]}).encode())

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
        self.wfile.write(json.dumps({"choices": [{"message": {"content": "OK"}}]}).encode())

    def log_message(self, format, *args):  # noqa: N802,A002
        return


def test_prewarm_selected_loopback_openai_provider_without_credentials(tmp_path: Path) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _WarmServer)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        pm = ProviderManager(tmp_path)
        pm.add(Provider(
            id="mtplx", name="MTPLX", kind=ProviderKind.LOCAL,
            transport="openai_compatible",
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            context_limit=262144, enabled=True, selected=True,
            models=["qwen3.8-27b-mtplx"],
        ))
        result = pm.prewarm("mtplx", "qwen3.8-27b-mtplx")
        assert result["status"] == "warm"
        assert result["endpoint_class"] == "local"
        assert result["provider"] == "mtplx"
        assert result["model"] == "qwen3.8-27b-mtplx"
        assert result["latency_ms"] >= 0
        assert _WarmServer.seen["path"] == "/v1/chat/completions"
        assert _WarmServer.seen["auth"] is None
        assert _WarmServer.seen["body"]["max_tokens"] <= 8
        assert _WarmServer.seen["body"]["model"] == "qwen3.8-27b-mtplx"
    finally:
        server.shutdown(); server.server_close()


def test_prewarm_rejects_non_loopback_local_label(tmp_path: Path) -> None:
    pm = ProviderManager(tmp_path)
    pm.add(Provider(
        id="spoof", name="Spoof", kind=ProviderKind.LOCAL,
        transport="openai_compatible", base_url="https://example.com/v1",
        enabled=True, selected=True, models=["model"],
    ))
    with pytest.raises(ValueError, match="loopback"):
        pm.prewarm("spoof", "model")


def test_prewarm_rejects_cloud_provider(tmp_path: Path) -> None:
    pm = ProviderManager(tmp_path)
    pm.add(Provider(
        id="cloud", name="Cloud", kind=ProviderKind.CLOUD,
        transport="openai_compatible", base_url="https://example.com/v1",
        enabled=True, selected=True, models=["model"],
    ))
    with pytest.raises(ValueError, match="local OpenAI-compatible"):
        pm.prewarm("cloud", "model")
