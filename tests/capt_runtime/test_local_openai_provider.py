from __future__ import annotations

import hashlib
import json
import subprocess
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


def _skill_pack(tmp_path: Path) -> tuple[Path, dict]:
    root = tmp_path / "CAPT_Skills"
    root.mkdir()
    for args in (("init", "-b", "main"), ("config", "user.email", "tests@example.invalid"),
                 ("config", "user.name", "CAPT Tests"),
                 ("remote", "add", "origin", "https://github.com/knowurknottty/CAPT_Skills.git")):
        subprocess.check_call(["git", "-C", str(root), *args])
    name = "inversion-interface-craft"
    path = root / "skills" / name / "SKILL.md"
    path.parent.mkdir(parents=True)
    content = "---\nname: %s\nversion: 0.1.0\n---\n\nPinned provider guidance: KEEP_UNKNOWN_UNKNOWN.\n" % name
    path.write_text(content)
    subprocess.check_call(["git", "-C", str(root), "add", "."])
    subprocess.check_call(["git", "-C", str(root), "commit", "-m", "fixture"])
    git = lambda *args: subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()
    return root, {
        "schemaVersion": "1.0.0", "packName": "CAPT_Skills", "packVersion": "0.1.0",
        "repository": "https://github.com/knowurknottty/CAPT_Skills.git", "ref": "v0.1.0",
        "commit": git("rev-parse", "HEAD"), "tree": git("rev-parse", "HEAD^{tree}"),
        "skills": [{"name": name, "version": "0.1.0", "path": f"skills/{name}/SKILL.md",
                    "sha256": hashlib.sha256(content.encode()).hexdigest()}],
    }


def test_runtime_dispatches_credentialless_local_openai_provider(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("CAPT_PROVIDER_KEY_MTPLX", raising=False)
    target = tmp_path / "target"
    target.mkdir()
    (target / "README.md").write_text("local provider regression\n")
    import capt_runtime.authored_skills as authored
    skill_root, skill_lock = _skill_pack(tmp_path)
    monkeypatch.setattr(authored, "load_capt_skills_lock", lambda _path=None: skill_lock)

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
            "skillPackRoot": str(skill_root),
            "skillNames": ["inversion-interface-craft"],
            "expiresAt": "2030-01-01T00:00:00Z",
        }, "local-noauth-approval")
        assert approval["status"] == "accepted"
        planned = approval["result"]
        decision = client.command("submit_approval_decision", {
            "requestId": planned["requestId"], "decision": "approve"
        }, "local-noauth-decision")
        assert decision["status"] == "accepted"
        run_payload = {
            "objective": objective,
            "targetRoot": str(target),
            "provider": "mtplx",
            "model": "qwen3.8-27b-mtplx",
            "skillPackRoot": str(skill_root),
            "skillNames": ["inversion-interface-craft"],
            "approvalRequestId": planned["requestId"],
            "missionId": planned["missionId"],
            "taskId": planned["taskId"],
            "driverRunId": planned["driverRunId"],
        }
        skill_file = skill_root / skill_lock["skills"][0]["path"]
        approved_bytes = skill_file.read_text()
        skill_file.write_text(approved_bytes + "\nTAMPER_AFTER_APPROVAL\n")
        tampered = client.command(
            "run_approved_hermes_inspection", run_payload, "local-noauth-run-tampered"
        )
        assert tampered["status"] == "rejected", tampered
        approval_state = client.get_state("human_approval-" + planned["requestId"])
        assert approval_state["state"] == "approved"
        assert approval_state["remainingUses"] == 1
        skill_file.write_text(approved_bytes)
        run = client.command("run_approved_hermes_inspection", run_payload, "local-noauth-run")
        assert run["status"] == "accepted", run
        assert run["result"]["observations"][0]["summary"] == "CAPT_LOCAL_NOAUTH_OK"
        assert run["result"]["providerProvenance"]["endpointClass"] == "local"
        authored = run["result"]["authoredSkills"]
        assert authored["sourceCommit"] == skill_lock["commit"]
        assert authored["skills"][0]["name"] == "inversion-interface-craft"
        assert "content" not in authored["skills"][0]
        assert _LocalOpenAIHandler.seen["path"] == "/v1/chat/completions"
        assert _LocalOpenAIHandler.seen["auth"] is None
        outbound = _LocalOpenAIHandler.seen["body"]["messages"][0]["content"]
        assert outbound.count("KEEP_UNKNOWN_UNKNOWN") == 1
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
