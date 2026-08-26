from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from capt_ui.operator.contract import ProviderKind
from capt_ui.operator.providers import Provider, ProviderManager
from desktop.capt_runtime_service import serve
from desktop.desktop_runtime_client import RuntimeClient


class _LocalOpenAIHandler(BaseHTTPRequestHandler):
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
        self.wfile.write(json.dumps({
            "choices": [{"message": {"content": "CAPT_LOCAL_NOAUTH_OK"}}]
        }).encode())

    def log_message(self, format, *args):  # noqa: N802,A002
        return


def _wait_for(path: Path, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return
        time.sleep(0.02)
    raise AssertionError(f"timed out waiting for {path}")


def test_runtime_dispatches_credentialless_local_openai_provider(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("CAPT_PROVIDER_KEY_MTPLX", raising=False)
    target = tmp_path / "target"
    target.mkdir()
    (target / "README.md").write_text("local provider regression\n")

    upstream = ThreadingHTTPServer(("127.0.0.1", 0), _LocalOpenAIHandler)
    upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    upstream_thread.start()

    state = tmp_path / "state"
    ui = state / "ui"
    pm = ProviderManager(ui)
    pm.add(Provider(
        id="mtplx",
        name="MTPLX Local",
        kind=ProviderKind.LOCAL,
        transport="openai_compatible",
        base_url=f"http://127.0.0.1:{upstream.server_port}/v1",
        context_limit=262144,
        enabled=True,
    ))

    ledger = state / "runtime.db"
    sock = state / "runtime.sock"
    token = state / "runtime.token"
    state.mkdir(parents=True, exist_ok=True)
    runtime_thread = threading.Thread(
        target=serve, args=(str(ledger), sock, str(token), False), daemon=True
    )
    runtime_thread.start()
    _wait_for(sock)
    _wait_for(token)

    client = RuntimeClient(str(sock), str(token))
    try:
        client.connect()
        objective = "Reply with exactly CAPT_LOCAL_NOAUTH_OK and no other text."
        approval = client.command("request_model_prompt_approval", {
            "objective": objective,
            "targetRoot": str(target),
            "provider": "mtplx",
            "model": "qwen3.8-27b-mtplx",
            "expiresAt": "2030-01-01T00:00:00Z",
        }, "local-noauth-approval")
        assert approval["status"] == "accepted"
        planned = approval["result"]
        decision = client.command("submit_approval_decision", {
            "requestId": planned["requestId"], "decision": "approve"
        }, "local-noauth-decision")
        assert decision["status"] == "accepted"
        run = client.command("run_approved_hermes_inspection", {
            "objective": objective,
            "targetRoot": str(target),
            "provider": "mtplx",
            "model": "qwen3.8-27b-mtplx",
            "approvalRequestId": planned["requestId"],
            "missionId": planned["missionId"],
            "taskId": planned["taskId"],
            "driverRunId": planned["driverRunId"],
        }, "local-noauth-run")
        assert run["status"] == "accepted", run
        assert run["result"]["observations"][0]["summary"] == "CAPT_LOCAL_NOAUTH_OK"
        assert run["result"]["providerProvenance"]["endpointClass"] == "local"
        assert _LocalOpenAIHandler.seen["path"] == "/v1/chat/completions"
        assert _LocalOpenAIHandler.seen["auth"] is None
    finally:
        try:
            client.command("shutdown", {}, "local-noauth-shutdown")
        except Exception:
            pass
        client.disconnect()
        upstream.shutdown()
        upstream.server_close()


def test_credentialless_policy_cannot_be_bypassed_by_local_label() -> None:
    from capt_runtime.provider_endpoint import credential_required, endpoint_class

    assert endpoint_class("http://127.0.0.1:18085/v1") == "local"
    assert endpoint_class("http://localhost:18085/v1") == "local"
    assert credential_required("mtplx", ProviderKind.LOCAL, "http://127.0.0.1:18085/v1") is False
    assert credential_required("fake-local", ProviderKind.LOCAL, "https://example.com/v1") is True
    assert credential_required("cloud-on-loopback", ProviderKind.CLOUD, "http://127.0.0.1:18085/v1") is True


def test_runtime_managed_skill_context_is_bound_identically_through_dispatch(
    tmp_path: Path, monkeypatch
) -> None:
    """Regression: approval-selected skill bytes must survive prepare/dispatch unchanged."""
    from capt_runtime.managed_skills import import_managed_skill_pack

    monkeypatch.delenv("CAPT_PROVIDER_KEY_MTPLX", raising=False)
    target = tmp_path / "target-managed"
    target.mkdir()
    (target / "README.md").write_text("managed skill dispatch regression\n")

    state = tmp_path / "state-managed"
    source = tmp_path / "skill-source"
    skill = source / "inversion-execute-now"
    skill.mkdir(parents=True)
    skill.joinpath("SKILL.md").write_text(
        "---\n"
        "name: inversion-execute-now\n"
        "description: Use when the user says proceed, continue, apply it, approved, or ship it.\n"
        "version: 1.0.0\n"
        "---\n\n"
        "# Execute Now\n\nCAPT_MANAGED_SKILL_MARKER\n"
    )
    import_managed_skill_pack(source, state / "skills" / "ultimate", pack_name="ultimate")

    upstream = ThreadingHTTPServer(("127.0.0.1", 0), _LocalOpenAIHandler)
    threading.Thread(target=upstream.serve_forever, daemon=True).start()
    pm = ProviderManager(state / "ui")
    pm.add(Provider(
        id="mtplx", name="MTPLX Local", kind=ProviderKind.LOCAL,
        transport="openai_compatible",
        base_url=f"http://127.0.0.1:{upstream.server_port}/v1",
        context_limit=262144, enabled=True,
    ))

    ledger, sock, token = state / "runtime.db", state / "runtime.sock", state / "runtime.token"
    state.mkdir(parents=True, exist_ok=True)
    threading.Thread(
        target=serve, args=(str(ledger), sock, str(token), False), daemon=True
    ).start()
    _wait_for(sock); _wait_for(token)

    client = RuntimeClient(str(sock), str(token))
    try:
        client.connect()
        objective = "Proceed and ship this release candidate once mergeable."
        approval = client.command("request_model_prompt_approval", {
            "objective": objective, "targetRoot": str(target),
            "provider": "mtplx", "model": "qwen3.8-27b-mtplx",
            "expiresAt": "2030-01-01T00:00:00Z",
        }, "managed-skill-approval")
        assert approval["status"] == "accepted", approval
        planned = approval["result"]
        assert planned["skillNames"] == ["inversion-execute-now"]
        assert client.command("submit_approval_decision", {
            "requestId": planned["requestId"], "decision": "approve"
        }, "managed-skill-decision")["status"] == "accepted"

        run = client.command("run_approved_hermes_inspection", {
            "objective": objective, "targetRoot": str(target),
            "provider": "mtplx", "model": "qwen3.8-27b-mtplx",
            "approvalRequestId": planned["requestId"],
            "missionId": planned["missionId"], "taskId": planned["taskId"],
            "driverRunId": planned["driverRunId"],
        }, "managed-skill-run")
        assert run["status"] == "accepted", run
        assert run["result"]["authoredSkills"]["trust"] == "managed_local"
        assert run["result"]["authoredSkills"]["skills"][0]["name"] == "inversion-execute-now"
        sent = _LocalOpenAIHandler.seen["body"]["messages"][0]["content"]
        assert "CAPT_MANAGED_SKILL_MARKER" in sent
    finally:
        try:
            client.command("shutdown", {}, "managed-skill-shutdown")
        except Exception:
            pass
        client.disconnect()
        upstream.shutdown()
        upstream.server_close()
