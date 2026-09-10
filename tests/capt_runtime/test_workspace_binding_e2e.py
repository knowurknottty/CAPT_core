from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from capt_ui.operator.contract import ProviderKind
from capt_ui.operator.providers import Provider, ProviderManager
from desktop.capt_runtime_service import serve
from desktop.desktop_runtime_client import RuntimeClient


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "choices": [{"message": {"content": "WORKSPACE_BINDING_OK"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2},
        }).encode())

    def log_message(self, format, *args):  # noqa: A002
        return


def _wait(path: Path) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if path.exists():
            return
        time.sleep(0.02)
    raise AssertionError(f"timeout waiting for {path}")


def test_external_symlink_root_is_bound_end_to_end(tmp_path: Path) -> None:
    real = tmp_path / "external-repo"
    real.mkdir()
    (real / "README.md").write_text("external repo\n")
    link = tmp_path / "external-link"
    link.symlink_to(real, target_is_directory=True)

    upstream = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=upstream.serve_forever, daemon=True).start()
    state = tmp_path / "state"
    state.mkdir()
    pm = ProviderManager(state / "ui")
    pm.add(Provider(
        id="workspace-e2e",
        name="Workspace E2E",
        kind=ProviderKind.LOCAL,
        transport="openai_compatible",
        base_url=f"http://127.0.0.1:{upstream.server_port}/v1",
        context_limit=32768,
        enabled=True,
    ))
    sock = state / "runtime.sock"
    token = state / "runtime.token"
    threading.Thread(
        target=serve,
        args=(str(state / "runtime.db"), sock, str(token), False),
        daemon=True,
    ).start()
    _wait(sock)
    _wait(token)
    client = RuntimeClient(str(sock), str(token))
    try:
        client.connect()
        objective = "Reply with exactly WORKSPACE_BINDING_OK."
        approval = client.command("request_model_prompt_approval", {
            "objective": objective,
            "targetRoot": str(link),
            "provider": "workspace-e2e",
            "model": "local-test",
            "autoSelectSkills": False,
            "expiresAt": "2030-01-01T00:00:00Z",
        }, "workspace-e2e-approval")
        assert approval["status"] == "accepted", approval
        planned = approval["result"]
        canonical = str(real.resolve())
        assert planned["authorityProfile"]["filesystemRoot"] == canonical
        state_row = client.get_state("human_approval-" + planned["requestId"])
        assert state_row["resource"] == canonical
        assert state_row["scope"]["rootPath"] == canonical
        assert state_row["scope"]["approvalBinding"]["targetRoot"] == canonical

        decision = client.command("submit_approval_decision", {
            "requestId": planned["requestId"], "decision": "approve"
        }, "workspace-e2e-decision")
        assert decision["status"] == "accepted"
        run = client.command("run_approved_hermes_inspection", {
            "objective": objective,
            "targetRoot": str(link),
            "provider": "workspace-e2e",
            "model": "local-test",
            "approvalRequestId": planned["requestId"],
            "missionId": planned["missionId"],
            "taskId": planned["taskId"],
            "driverRunId": planned["driverRunId"],
            "autoSelectSkills": False,
        }, "workspace-e2e-run")
        assert run["status"] == "accepted", run
        result = run["result"]
        assert result["targetPath"] == canonical
        baseline = json.loads(Path(result["verificationBaselinePath"]).read_text())
        assert baseline["targetRoot"] == canonical
        assert result["observations"][0]["summary"] == "WORKSPACE_BINDING_OK"
    finally:
        try:
            client.command("shutdown", {}, "workspace-e2e-shutdown")
        except Exception:
            pass
        client.disconnect()
        upstream.shutdown()
        upstream.server_close()
