"""CAPT-UPG-027: credentialed outbound HTTP must never follow redirects.

CPython's default urllib opener re-issues a 301/302/303 POST as a GET to the
``Location`` origin and forwards the ``Authorization`` header across origins.
"""
from __future__ import annotations

import ast
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from capt_runtime import http_client
from capt_runtime.billing_assurance import (
    BillingAssuranceError,
    verify_openrouter_key_limit,
)

REPO = Path(__file__).resolve().parents[2]
SHIPPED = ("capt_runtime", "capt_ui", "capt_solo", "desktop")


class _Recorder:
    def __init__(self) -> None:
        self.requests: list[dict[str, str | None]] = []


def _serve(handler: type[BaseHTTPRequestHandler], host: str) -> HTTPServer:
    server = HTTPServer((host, 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.fixture()
def redirect_pair() -> Iterator[tuple[str, _Recorder]]:
    """Origin A answers every request with a 302 to origin B, which records."""
    seen = _Recorder()

    class Target(BaseHTTPRequestHandler):
        def _record(self) -> None:
            seen.requests.append({
                "method": self.command,
                "authorization": self.headers.get("Authorization"),
            })
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"data": {}}')

        do_GET = do_POST = _record

        def log_message(self, *_args: object) -> None:
            pass

    # An independent ephemeral port is a distinct HTTP origin without
    # relying on 127.0.0.2 being configured as a loopback alias (it is not
    # guaranteed on macOS). The security test still checks zero forwarding.
    target = _serve(Target, "127.0.0.1")

    class Origin(BaseHTTPRequestHandler):
        def _redirect(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                self.rfile.read(length)
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{target.server_port}/steal")
            self.send_header("Content-Length", "0")
            self.end_headers()

        do_GET = do_POST = _redirect

        def log_message(self, *_args: object) -> None:
            pass

    origin = _serve(Origin, "127.0.0.1")
    try:
        yield f"http://127.0.0.1:{origin.server_port}", seen
    finally:
        origin.shutdown()
        target.shutdown()
        origin.server_close()
        target.server_close()


def test_open_url_refuses_redirect_and_target_sees_nothing(redirect_pair: tuple[str, _Recorder]) -> None:
    base, seen = redirect_pair
    request = urllib.request.Request(
        base + "/v1/chat/completions", data=b"{}", method="POST",
        headers={"Authorization": "Bearer sk-SECRET", "Content-Type": "application/json"},
    )
    with pytest.raises(urllib.error.HTTPError) as caught:
        http_client.open_url(request, timeout=5)
    assert caught.value.code == 302
    assert seen.requests == []


def test_billing_assurance_does_not_forward_key_on_redirect(redirect_pair: tuple[str, _Recorder]) -> None:
    base, seen = redirect_pair
    with pytest.raises(BillingAssuranceError):
        verify_openrouter_key_limit("sk-SECRET", source_sha="0" * 40, endpoint=base + "/api/v1/key")
    assert seen.requests == []


def test_read_bounded_rejects_oversize_body() -> None:
    class Body:
        def __init__(self, payload: bytes) -> None:
            self.payload = payload

        def read(self, size: int = -1) -> bytes:
            return self.payload if size < 0 else self.payload[:size]

    assert http_client.read_bounded(Body(b"x" * 10), limit=10) == b"x" * 10
    with pytest.raises(http_client.ResponseTooLarge):
        http_client.read_bounded(Body(b"x" * 11), limit=10)
    with pytest.raises(ValueError):
        http_client.read_bounded(Body(b""), limit=0)


def _python_files() -> Iterator[Path]:
    for package in SHIPPED:
        yield from sorted((REPO / package).rglob("*.py"))
    yield REPO / "capt_cli.py"


def test_no_default_redirecting_opener_in_shipped_code() -> None:
    """Gate: shipped code reaches the network only through a no-redirect opener."""
    offenders: list[str] = []
    for path in _python_files():
        rel = path.relative_to(REPO).as_posix()
        if rel == "capt_runtime/http_client.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = ast.unparse(node.func)
            if name.endswith("urlopen"):
                offenders.append(f"{rel}:{node.lineno}: {name}")
            elif name.endswith("build_opener"):
                handlers = [ast.unparse(arg) for arg in node.args]
                if not any("NoRedirect" in h for h in handlers):
                    offenders.append(f"{rel}:{node.lineno}: build_opener without a no-redirect handler")
    assert offenders == []
