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
            "requestedExecutionSeconds": 1800,
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
            "requestedExecutionSeconds": 60,
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
        assert run["result"]["providerProvenance"]["contextBudgetTokens"] == 32_000
        assert run["result"]["providerProvenance"]["requestTimeoutBudgetSeconds"] == 1800.0
        mission_state = client.get_state("mission-" + planned["missionId"])
        assert mission_state["state"] == "executing"
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


def test_runtime_auto_selects_managed_skill_and_rejects_post_approval_tamper(tmp_path: Path, monkeypatch) -> None:
    from capt_runtime.managed_skills import import_managed_skill_pack

    monkeypatch.delenv("CAPT_PROVIDER_KEY_MTPLX", raising=False)
    target = tmp_path / "target"
    target.mkdir()
    (target / "README.md").write_text("managed skill runtime regression\n")

    state = tmp_path / "state"
    source = tmp_path / "managed-source"
    skill = source / "inversion-execute-now"
    skill.mkdir(parents=True)
    marker = "MANAGED_EXECUTE_MARKER"
    skill.joinpath("SKILL.md").write_text(
        "---\n"
        "name: inversion-execute-now\n"
        "description: Use when the user says proceed, continue, apply it, approved, or ship it.\n"
        "version: 1.0.0\n"
        "---\n\n"
        f"# Execute Now\n\n{marker}\n"
    )
    imported = import_managed_skill_pack(
        source, state / "skills" / "ultimate", pack_name="ultimate"
    )
    assert imported["skillCount"] == 1

    upstream = ThreadingHTTPServer(("127.0.0.1", 0), _LocalOpenAIHandler)
    upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    upstream_thread.start()

    ui = state / "ui"
    pm = ProviderManager(ui)
    pm.add(Provider(
        id="mtplx-managed",
        name="MTPLX Managed",
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
    _wait_for(sock); _wait_for(token)
    client = RuntimeClient(str(sock), str(token))
    try:
        client.connect()
        objective = "Proceed with this task and reply exactly CAPT_LOCAL_NOAUTH_OK."
        approval = client.command("request_model_prompt_approval", {
            "objective": objective,
            "targetRoot": str(target),
            "provider": "mtplx-managed",
            "model": "qwen3.8-27b-mtplx",
            "expiresAt": "2030-01-01T00:00:00Z",
        }, "managed-auto-approval")
        assert approval["status"] == "accepted", approval
        planned = approval["result"]
        assert planned["skillNames"] == ["inversion-execute-now"]
        assert planned["authoredSkills"]["trust"] == "managed_local"
        decision = client.command("submit_approval_decision", {
            "requestId": planned["requestId"], "decision": "approve"
        }, "managed-auto-decision")
        assert decision["status"] == "accepted"
        run_payload = {
            "objective": objective,
            "targetRoot": str(target),
            "provider": "mtplx-managed",
            "model": "qwen3.8-27b-mtplx",
            "approvalRequestId": planned["requestId"],
            "missionId": planned["missionId"],
            "taskId": planned["taskId"],
            "driverRunId": planned["driverRunId"],
        }
        installed = state / "skills" / "ultimate" / "skills" / "inversion-execute-now" / "SKILL.md"
        approved_bytes = installed.read_text()
        installed.write_text(approved_bytes + "\nTAMPER_AFTER_APPROVAL\n")
        tampered = client.command(
            "run_approved_hermes_inspection", run_payload, "managed-auto-run-tampered"
        )
        assert tampered["status"] == "rejected", tampered
        approval_state = client.get_state("human_approval-" + planned["requestId"])
        assert approval_state["state"] == "approved"
        assert approval_state["remainingUses"] == 1
        installed.write_text(approved_bytes)
        run = client.command("run_approved_hermes_inspection", run_payload, "managed-auto-run")
        assert run["status"] == "accepted", run
        assert run["result"]["authoredSkills"]["trust"] == "managed_local"
        assert run["result"]["authoredSkills"]["skills"][0]["name"] == "inversion-execute-now"
        outbound = _LocalOpenAIHandler.seen["body"]["messages"][0]["content"]
        assert outbound.count(marker) == 1
    finally:
        try:
            client.command("shutdown", {}, "managed-auto-shutdown")
        except Exception:
            pass
        client.disconnect()
        upstream.shutdown(); upstream.server_close()


class _GovernedToolHandler(BaseHTTPRequestHandler):
    calls = []

    def do_POST(self):  # noqa: N802
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        body = json.loads(raw)
        self.__class__.calls.append(body)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if len(self.__class__.calls) == 1 and body.get("tools"):
            payload = {
                "choices": [{"message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call-runtime-read-1",
                        "type": "function",
                        "function": {
                            "name": "capt_file_read",
                            "arguments": json.dumps({"path": "hello.txt"}),
                        },
                    }],
                }}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 4},
            }
        elif len(self.__class__.calls) > 1:
            payload = {
                "choices": [{"message": {
                    "role": "assistant",
                    "content": "CAPT_TOOL_AUTHORITY_OK",
                }}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 6},
            }
        else:
            payload = {"choices": [{"message": {"content": "TOOL_BRIDGE_MISSING"}}]}
        self.wfile.write(json.dumps(payload).encode())

    def log_message(self, format, *args):  # noqa: N802,A002
        return


def test_runtime_model_tools_flow_through_approval_toolbroker_and_phase_revocation(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("CAPT_PROVIDER_KEY_MTPLX_TOOLS", raising=False)
    target = tmp_path / "target-tools"
    target.mkdir()
    (target / "hello.txt").write_text("CAPT_RUNTIME_TOOL_READ_OK")

    upstream = ThreadingHTTPServer(("127.0.0.1", 0), _GovernedToolHandler)
    upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    upstream_thread.start()
    _GovernedToolHandler.calls = []

    state = tmp_path / "state-tools"
    ui = state / "ui"
    pm = ProviderManager(ui)
    pm.add(Provider(
        id="mtplx-tools",
        name="MTPLX Tools Local",
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
    _wait_for(sock); _wait_for(token)

    client = RuntimeClient(str(sock), str(token))
    try:
        client.connect()
        objective = "Read hello.txt using the governed filesystem tool and report the result."
        authority = {
            "filesystemScope": "project",
            "filesystemRoot": str(target),
            "fileMutationAllowed": False,
            "shellAccessAllowed": False,
            "providerNetworkPolicy": "local_only",
        }
        approval = client.command("request_model_prompt_approval", {
            "objective": objective,
            "targetRoot": str(target),
            "provider": "mtplx-tools",
            "model": "tool-model",
            "authorityProfile": authority,
            "autoSelectSkills": False,
            "expiresAt": "2030-01-01T00:00:00Z",
        }, "runtime-tools-approval")
        assert approval["status"] == "accepted", approval
        planned = approval["result"]
        assert planned["authorityProfile"]["toolOperations"] == ["file.read", "file.search"]
        assert client.command("submit_approval_decision", {
            "requestId": planned["requestId"], "decision": "approve"
        }, "runtime-tools-decision")["status"] == "accepted"

        run = client.command("run_approved_hermes_inspection", {
            "objective": objective,
            "targetRoot": str(target),
            "provider": "mtplx-tools",
            "model": "tool-model",
            "approvalRequestId": planned["requestId"],
            "missionId": planned["missionId"],
            "taskId": planned["taskId"],
            "driverRunId": planned["driverRunId"],
            "autoSelectSkills": False,
        }, "runtime-tools-run")
        assert run["status"] == "accepted", run
        assert run["result"]["observations"][0]["summary"] == "CAPT_TOOL_AUTHORITY_OK"
        assert run["result"]["providerProvenance"]["toolCallCount"] == 1
        assert len(_GovernedToolHandler.calls) == 2
        tool_message = next(
            item for item in _GovernedToolHandler.calls[1]["messages"]
            if item["role"] == "tool"
        )
        tool_result = json.loads(tool_message["content"])
        assert tool_result["status"] == "succeeded"
        assert tool_result["values"]["content"] == "CAPT_RUNTIME_TOOL_READ_OK"
        execution = client.get_state("tool_execution-" + tool_result["toolExecutionId"])
        assert execution["operation"] == "file.read"
        capability = client.get_state("capability-" + execution["grantId"])
        assert capability["revocation"] is not None
        assert capability["revocation"]["reason"] == "provider tool phase closed"
    finally:
        try:
            client.command("shutdown", {}, "runtime-tools-shutdown")
        except Exception:
            pass
        client.disconnect()
        upstream.shutdown(); upstream.server_close()


class _AuthorityMatrixHandler(BaseHTTPRequestHandler):
    calls = []
    tool_name = ""
    tool_arguments = {}
    final_text = "AUTHORITY_MATRIX_OK"

    def do_POST(self):  # noqa: N802
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        body = json.loads(raw)
        self.__class__.calls.append(body)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if len(self.__class__.calls) == 1:
            payload = {
                "choices": [{"message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call-authority-matrix",
                        "type": "function",
                        "function": {
                            "name": self.__class__.tool_name,
                            "arguments": json.dumps(self.__class__.tool_arguments),
                        },
                    }],
                }}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 4},
            }
        else:
            payload = {
                "choices": [{"message": {
                    "role": "assistant",
                    "content": self.__class__.final_text,
                }}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 6},
            }
        self.wfile.write(json.dumps(payload).encode())

    def log_message(self, format, *args):  # noqa: N802,A002
        return


def _run_runtime_authority_matrix_case(
    tmp_path: Path,
    monkeypatch,
    *,
    case: str,
    tool_name: str,
    tool_arguments: dict,
    mutation: bool,
    shell: bool,
):
    target = tmp_path / ("target-" + case)
    target.mkdir()
    _AuthorityMatrixHandler.calls = []
    _AuthorityMatrixHandler.tool_name = tool_name
    _AuthorityMatrixHandler.tool_arguments = dict(tool_arguments)
    _AuthorityMatrixHandler.final_text = "AUTHORITY_MATRIX_OK:" + case
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), _AuthorityMatrixHandler)
    threading.Thread(target=upstream.serve_forever, daemon=True).start()

    state = tmp_path / ("state-" + case)
    provider_id = "matrix-" + case
    ProviderManager(state / "ui").add(Provider(
        id=provider_id,
        name="Matrix " + case,
        kind=ProviderKind.LOCAL,
        transport="openai_compatible",
        base_url=f"http://127.0.0.1:{upstream.server_port}/v1",
        context_limit=262144,
        enabled=True,
    ))
    ledger = state / "runtime.db"
    # macOS AF_UNIX paths are short; pytest's descriptive tmp_path can exceed
    # sockaddr_un.sun_path. Keep authoritative state under tmp_path, but place
    # only the ephemeral IPC socket at a deterministic short /tmp path.
    socket_tag = hashlib.sha256((str(tmp_path) + ":" + case).encode()).hexdigest()[:12]
    sock = Path("/tmp") / ("capt-matrix-" + socket_tag + ".sock")
    token = state / "runtime.token"
    state.mkdir(parents=True, exist_ok=True)
    threading.Thread(
        target=serve, args=(str(ledger), sock, str(token), False), daemon=True
    ).start()
    _wait_for(sock); _wait_for(token)
    client = RuntimeClient(str(sock), str(token))
    client.connect()
    authority = {
        "filesystemScope": "project",
        "filesystemRoot": str(target),
        "fileMutationAllowed": mutation,
        "shellAccessAllowed": shell,
        "providerNetworkPolicy": "local_only",
    }
    objective = "Exercise the governed authority matrix for " + case
    approval = client.command("request_model_prompt_approval", {
        "objective": objective,
        "targetRoot": str(target),
        "provider": provider_id,
        "model": "tool-model",
        "authorityProfile": authority,
        "autoSelectSkills": False,
        "expiresAt": "2030-01-01T00:00:00Z",
    }, case + "-approval")
    assert approval["status"] == "accepted", approval
    planned = approval["result"]
    assert client.command("submit_approval_decision", {
        "requestId": planned["requestId"], "decision": "approve"
    }, case + "-decision")["status"] == "accepted"
    run = client.command("run_approved_hermes_inspection", {
        "objective": objective,
        "targetRoot": str(target),
        "provider": provider_id,
        "model": "tool-model",
        "approvalRequestId": planned["requestId"],
        "missionId": planned["missionId"],
        "taskId": planned["taskId"],
        "driverRunId": planned["driverRunId"],
        "autoSelectSkills": False,
    }, case + "-run")
    return client, upstream, target, planned, run


def test_runtime_write_authority_off_rejects_model_write_before_mutation(tmp_path: Path, monkeypatch) -> None:
    target_path = "written.txt"
    client, upstream, target, _planned, run = _run_runtime_authority_matrix_case(
        tmp_path, monkeypatch,
        case="write-off",
        tool_name="capt_file_write",
        tool_arguments={"path": target_path, "content": "SHOULD_NOT_EXIST"},
        mutation=False,
        shell=False,
    )
    try:
        assert run["status"] == "rejected", run
        assert "MODEL_TOOL_NOT_AUTHORIZED:file.write" in (run.get("detail") or "")
        assert not (target / target_path).exists()
        assert len(_AuthorityMatrixHandler.calls) == 1
    finally:
        try: client.command("shutdown", {}, "write-off-shutdown")
        except Exception: pass
        client.disconnect(); upstream.shutdown(); upstream.server_close()


def test_runtime_write_authority_on_executes_world_receipt_path(tmp_path: Path, monkeypatch) -> None:
    target_path = "written.txt"
    client, upstream, target, _planned, run = _run_runtime_authority_matrix_case(
        tmp_path, monkeypatch,
        case="write-on",
        tool_name="capt_file_write",
        tool_arguments={"path": target_path, "content": "WRITE_AUTHORITY_OK"},
        mutation=True,
        shell=False,
    )
    try:
        assert run["status"] == "accepted", run
        assert (target / target_path).read_text() == "WRITE_AUTHORITY_OK"
        tool_msg = next(x for x in _AuthorityMatrixHandler.calls[1]["messages"] if x["role"] == "tool")
        tool_result = json.loads(tool_msg["content"])
        assert tool_result["status"] == "succeeded"
        execution = client.get_state("tool_execution-" + tool_result["toolExecutionId"])
        assert execution["operation"] == "file.write"
        assert execution["worldReceipt"] is not None
        assert execution["settlementStatus"] == "settled"
    finally:
        try: client.command("shutdown", {}, "write-on-shutdown")
        except Exception: pass
        client.disconnect(); upstream.shutdown(); upstream.server_close()


def test_runtime_shell_authority_off_rejects_model_shell(tmp_path: Path, monkeypatch) -> None:
    client, upstream, _target, _planned, run = _run_runtime_authority_matrix_case(
        tmp_path, monkeypatch,
        case="shell-off",
        tool_name="capt_shell_exec",
        tool_arguments={"argv": ["/bin/echo", "SHOULD_NOT_RUN"]},
        mutation=False,
        shell=False,
    )
    try:
        assert run["status"] == "rejected", run
        assert "MODEL_TOOL_NOT_AUTHORIZED:terminal.exec" in (run.get("detail") or "")
        assert len(_AuthorityMatrixHandler.calls) == 1
    finally:
        try: client.command("shutdown", {}, "shell-off-shutdown")
        except Exception: pass
        client.disconnect(); upstream.shutdown(); upstream.server_close()


def test_runtime_shell_authority_on_executes_terminal_toolbroker_path(tmp_path: Path, monkeypatch) -> None:
    client, upstream, _target, _planned, run = _run_runtime_authority_matrix_case(
        tmp_path, monkeypatch,
        case="shell-on",
        tool_name="capt_shell_exec",
        tool_arguments={"argv": ["/bin/echo", "SHELL_AUTHORITY_OK"]},
        mutation=False,
        shell=True,
    )
    try:
        assert run["status"] == "accepted", run
        tool_msg = next(x for x in _AuthorityMatrixHandler.calls[1]["messages"] if x["role"] == "tool")
        tool_result = json.loads(tool_msg["content"])
        assert tool_result["status"] == "succeeded"
        assert "SHELL_AUTHORITY_OK" in tool_result["values"]["stdout"]
        execution = client.get_state("tool_execution-" + tool_result["toolExecutionId"])
        assert execution["operation"] == "terminal.exec"
        assert execution["state"] == "completed"
    finally:
        try: client.command("shutdown", {}, "shell-on-shutdown")
        except Exception: pass
        client.disconnect(); upstream.shutdown(); upstream.server_close()


def test_runtime_local_only_blocks_remote_provider_before_credential_resolution(tmp_path: Path, monkeypatch) -> None:
    provider_id = "remote-blocked"
    monkeypatch.delenv("CAPT_PROVIDER_KEY_REMOTE-BLOCKED", raising=False)
    target = tmp_path / "target-remote-blocked"
    target.mkdir()
    state = tmp_path / "state-remote-blocked"
    state.mkdir(parents=True, exist_ok=True)
    ProviderManager(state / "ui").add(Provider(
        id=provider_id,
        name="Remote Blocked",
        kind=ProviderKind.CLOUD,
        transport="openai_compatible",
        base_url="https://capt-remote.invalid/v1",
        context_limit=128000,
        enabled=True,
    ))
    tag = hashlib.sha256(str(tmp_path).encode()).hexdigest()[:12]
    sock = Path("/tmp") / ("capt-net-off-" + tag + ".sock")
    token = state / "runtime.token"
    threading.Thread(
        target=serve,
        args=(str(state / "runtime.db"), sock, str(token), False),
        daemon=True,
    ).start()
    _wait_for(sock); _wait_for(token)
    client = RuntimeClient(str(sock), str(token))
    try:
        client.connect()
        objective = "Provider network policy rejection proof."
        approval = client.command("request_model_prompt_approval", {
            "objective": objective,
            "targetRoot": str(target),
            "provider": provider_id,
            "model": "remote-model",
            "authorityProfile": {
                "filesystemScope": "project",
                "filesystemRoot": str(target),
                "fileMutationAllowed": False,
                "shellAccessAllowed": False,
                "providerNetworkPolicy": "local_only",
            },
            "autoSelectSkills": False,
            "expiresAt": "2030-01-01T00:00:00Z",
        }, "remote-blocked-approval")
        assert approval["status"] == "accepted", approval
        planned = approval["result"]
        assert client.command("submit_approval_decision", {
            "requestId": planned["requestId"], "decision": "approve"
        }, "remote-blocked-decision")["status"] == "accepted"
        run = client.command("run_approved_hermes_inspection", {
            "objective": objective,
            "targetRoot": str(target),
            "provider": provider_id,
            "model": "remote-model",
            "approvalRequestId": planned["requestId"],
            "missionId": planned["missionId"],
            "taskId": planned["taskId"],
            "driverRunId": planned["driverRunId"],
            "autoSelectSkills": False,
        }, "remote-blocked-run")
        assert run["status"] == "rejected", run
        assert run["classification"] == "authority", run
        assert run["detail"] == "REMOTE_PROVIDER_NETWORK_NOT_AUTHORIZED"
    finally:
        try: client.command("shutdown", {}, "remote-blocked-shutdown")
        except Exception: pass
        client.disconnect()


def test_runtime_remote_allowed_dispatches_cloud_provider_after_approval(tmp_path: Path, monkeypatch) -> None:
    import io
    import capt_runtime.drivers.provider as provider_driver_module

    provider_id = "remote-allowed"
    secret = "remote-test-secret-12345"
    monkeypatch.setenv("CAPT_TEST_REMOTE_KEY", secret)
    target = tmp_path / "target-remote-allowed"
    target.mkdir()
    state = tmp_path / "state-remote-allowed"
    state.mkdir(parents=True, exist_ok=True)
    ProviderManager(state / "ui").add(Provider(
        id=provider_id,
        name="Remote Allowed",
        kind=ProviderKind.CLOUD,
        transport="openai_compatible",
        base_url="https://capt-remote.invalid/v1",
        key_ref="env:CAPT_TEST_REMOTE_KEY",
        context_limit=128000,
        enabled=True,
    ))

    seen = []
    class _FakeHTTPResponse:
        def __init__(self, payload: dict):
            self._raw = json.dumps(payload).encode()
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self): return self._raw

    def fake_urlopen(request, timeout=0):
        seen.append({
            "url": request.full_url,
            "authorization": request.get_header("Authorization"),
            "body": json.loads(request.data.decode()),
            "timeout": timeout,
        })
        return _FakeHTTPResponse({
            "choices": [{"message": {"role": "assistant", "content": "REMOTE_AUTHORITY_OK"}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 5},
        })

    monkeypatch.setattr(provider_driver_module.urllib.request, "urlopen", fake_urlopen)
    tag = hashlib.sha256(str(tmp_path).encode()).hexdigest()[:12]
    sock = Path("/tmp") / ("capt-net-on-" + tag + ".sock")
    token = state / "runtime.token"
    threading.Thread(
        target=serve,
        args=(str(state / "runtime.db"), sock, str(token), False),
        daemon=True,
    ).start()
    _wait_for(sock); _wait_for(token)
    client = RuntimeClient(str(sock), str(token))
    try:
        client.connect()
        objective = "Remote provider authority dispatch proof."
        approval = client.command("request_model_prompt_approval", {
            "objective": objective,
            "targetRoot": str(target),
            "provider": provider_id,
            "model": "remote-model",
            "authorityProfile": {
                "filesystemScope": "project",
                "filesystemRoot": str(target),
                "fileMutationAllowed": False,
                "shellAccessAllowed": False,
                "providerNetworkPolicy": "remote_allowed",
            },
            "autoSelectSkills": False,
            "expiresAt": "2030-01-01T00:00:00Z",
        }, "remote-allowed-approval")
        assert approval["status"] == "accepted", approval
        planned = approval["result"]
        assert planned["authorityProfile"]["providerNetworkPolicy"] == "remote_allowed"
        assert client.command("submit_approval_decision", {
            "requestId": planned["requestId"], "decision": "approve"
        }, "remote-allowed-decision")["status"] == "accepted"
        run = client.command("run_approved_hermes_inspection", {
            "objective": objective,
            "targetRoot": str(target),
            "provider": provider_id,
            "model": "remote-model",
            "approvalRequestId": planned["requestId"],
            "missionId": planned["missionId"],
            "taskId": planned["taskId"],
            "driverRunId": planned["driverRunId"],
            "autoSelectSkills": False,
        }, "remote-allowed-run")
        assert run["status"] == "accepted", run
        assert run["result"]["observations"][0]["summary"] == "REMOTE_AUTHORITY_OK"
        assert run["result"]["providerProvenance"]["endpointClass"] == "cloud"
        remote_calls = [item for item in seen if item["url"].startswith("https://capt-remote.invalid/")]
        assert len(remote_calls) == 1
        assert remote_calls[0]["url"] == "https://capt-remote.invalid/v1/chat/completions"
        assert remote_calls[0]["authorization"] == "Bearer " + secret
        assert [tool["function"]["name"] for tool in remote_calls[0]["body"]["tools"]] == [
            "capt_file_read", "capt_file_search"
        ]
    finally:
        try: client.command("shutdown", {}, "remote-allowed-shutdown")
        except Exception: pass
        client.disconnect()
