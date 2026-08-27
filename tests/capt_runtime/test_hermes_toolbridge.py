from __future__ import annotations

import json
import stat
from pathlib import Path

from capt_runtime.tool_broker import tool_request_fingerprint
from capt_runtime.hermes_toolbridge import (
    MCP_SERVER_NAME,
    ToolBridgeBinding,
    build_isolated_hermes_home,
    mcp_tool_definitions,
)


def test_mcp_surface_exposes_only_governed_broker_tools() -> None:
    names = {tool["name"] for tool in mcp_tool_definitions()}
    assert names == {
        "capt_terminal",
        "capt_read_file",
        "capt_search_files",
        "capt_write_file",
        "capt_patch_file",
    }
    assert "terminal" not in names
    assert "shell" not in names
    assert "file" not in names


def test_terminal_call_becomes_scoped_tool_request(tmp_path: Path) -> None:
    binding = ToolBridgeBinding(
        grant_id="g-toolbridge-1",
        lease_id="l-toolbridge-1",
        filesystem_scope=str(tmp_path),
        runtime_sock="/tmp/capt-runtime.sock",
        token_file="/tmp/capt-runtime.token",
    )
    request = binding.build_tool_request(
        "capt_terminal",
        {"argv": ["git", "status", "--short"], "cwd": ".", "timeout_ms": 120000},
        request_id="call-1",
        requested_at="2026-08-27T06:00:00Z",
    )
    assert request["toolId"] == "terminal.local"
    assert request["operation"] == "terminal.exec"
    assert request["backendId"] == "local"
    assert request["filesystemScope"] == str(tmp_path)
    assert request["grantId"] == "g-toolbridge-1"
    assert request["leaseId"] == "l-toolbridge-1"
    assert request["consequential"] is True
    assert request["operationFingerprint"] == tool_request_fingerprint(request)
    args = {item["name"]: item["value"] for item in request["arguments"]}
    assert json.loads(args["argv"]) == ["git", "status", "--short"]
    assert args["cwd"] == str(tmp_path)


def test_isolated_home_contains_only_capt_mcp_and_provider_secret(tmp_path: Path) -> None:
    home = build_isolated_hermes_home(
        tmp_path / "hermes-home",
        bridge_argv=["/usr/bin/python3", "-m", "capt_runtime.hermes_toolbridge", "serve"],
        provider="openrouter",
        model="z-ai/glm-5.3-flash",
        provider_api_key="secret-value",
    )
    config = (home / "config.yaml").read_text()
    assert f"{MCP_SERVER_NAME}:" in config
    assert "mcp_servers:" in config
    assert "terminal:" not in config
    assert "file:" not in config
    assert "provider: openrouter" in config
    assert "model: z-ai/glm-5.3-flash" in config
    env_path = home / ".env"
    assert env_path.read_text() == "OPENROUTER_API_KEY=secret-value\n"
    assert stat.S_IMODE(env_path.stat().st_mode) == 0o600
    assert stat.S_IMODE((home / "config.yaml").stat().st_mode) == 0o600


def test_mcp_protocol_routes_tool_call_to_broker_callback(tmp_path: Path) -> None:
    from capt_runtime.hermes_toolbridge import handle_mcp_message

    binding = ToolBridgeBinding(
        grant_id="g-toolbridge-2", lease_id="l-toolbridge-2",
        filesystem_scope=str(tmp_path), runtime_sock="/tmp/capt.sock", token_file="/tmp/capt.token",
    )
    initialized = handle_mcp_message(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}, binding, lambda _: None
    )
    assert initialized["result"]["capabilities"]["tools"] == {"listChanged": False}
    listed = handle_mcp_message(
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, binding, lambda _: None
    )
    assert {tool["name"] for tool in listed["result"]["tools"]} == {tool["name"] for tool in mcp_tool_definitions()}
    seen: list[dict] = []
    def execute(request: dict) -> dict:
        seen.append(request)
        return {"status": "accepted", "result": {"status": "succeeded", "output": [{"kind": "string", "name": "stdout", "value": "ok"}]}}
    called = handle_mcp_message(
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "capt_terminal", "arguments": {"argv": ["git", "status"], "cwd": "."}}},
        binding, execute,
    )
    assert seen and seen[0]["operation"] == "terminal.exec"
    assert called["result"]["isError"] is False
    assert "ok" in called["result"]["content"][0]["text"]


def test_runtime_executor_authenticates_and_uses_exact_tool_idempotency(tmp_path: Path) -> None:
    from capt_runtime.hermes_toolbridge import execute_via_runtime

    events: list[tuple] = []
    class FakeClient:
        def __init__(self, sock: str, token: str) -> None:
            events.append(("init", sock, token))
        def connect(self) -> None:
            events.append(("connect",))
        def command(self, op: str, payload: dict, idem: str) -> dict:
            events.append(("command", op, payload["toolRequestId"], idem))
            return {"status": "accepted", "result": {"status": "succeeded", "output": []}}
        def disconnect(self) -> None:
            events.append(("disconnect",))

    binding = ToolBridgeBinding(
        grant_id="g-toolbridge-3", lease_id="l-toolbridge-3",
        filesystem_scope=str(tmp_path), runtime_sock="/tmp/live.sock", token_file="/tmp/live.token",
    )
    request = binding.build_tool_request(
        "capt_read_file", {"path": "README.md"},
        request_id="mcp-17", requested_at="2026-08-27T06:10:00Z",
    )
    receipt = execute_via_runtime(binding, request, client_factory=FakeClient)
    assert receipt["status"] == "accepted"
    assert events == [
        ("init", "/tmp/live.sock", "/tmp/live.token"),
        ("connect",),
        ("command", "run_tool", request["toolRequestId"], request["idempotencyKey"]),
        ("disconnect",),
    ]


def _seed_read_authority(runtime, root: Path) -> tuple[str, str]:
    from capt_runtime import commands, contracts
    now = "2026-08-27T06:20:00Z"
    def meta(step: str, kind: str, actor: str) -> dict:
        return commands.command(
            command_id=f"cmd-tb-{step}", idempotency_key=f"idem-tb-{step}",
            operation_fingerprint=commands.fingerprint(step, {"step": step}),
            correlation_id="corr-toolbridge-live", actor_id=actor, actor_kind=kind,
            issued_at=now, replay_policy="never",
        )
    runtime.service.create_mission(
        {
            "schemaVersion": "1.0.0", "missionId": "m-toolbridge-live",
            "rawRequest": "bridge live read", "normalizedRequest": "bridge live read",
            "objectives": [{"objectiveId": "obj-1", "statement": "read through bridge", "priority": 1}],
            "constraints": [{"kind": "resource_boundary", "constraintId": "con-1", "origin": "explicit_user",
                             "scope": {"kind": "filesystem", "rootPath": str(root), "recursive": True}}],
            "successCriteria": [{"criterionId": "sc-1", "statement": "tool evidence recorded", "requiresVerification": True}],
            "terminationCriteria": [{"criterionId": "tc-1", "statement": "boundary violation", "terminalState": "failed"}],
            "unresolvedAmbiguities": [], "taskGraphId": None, "createdAt": now,
        }, meta("mission", "human", "operator-test")
    )
    digest = contracts.digest({"policy": "toolbridge-live"})
    runtime.service.evaluate_policy(
        {
            "schemaVersion": "1.0.0", "policyDecisionId": "pd-toolbridge-live",
            "policyBundleDigest": digest, "effect": "allow",
            "subject": {"actorId": "tool-broker", "kind": "execution_plane"},
            "missionId": "m-toolbridge-live", "taskId": "t-toolbridge-live",
            "requestedOperations": ["file.read"],
            "requestedScope": {"kind": "filesystem", "rootPath": str(root), "recursive": True},
            "conditions": [], "rationale": "bounded bridge integration",
            "decidedBy": {"actorId": "gk-1", "kind": "governance_kernel"}, "decidedAt": "2026-08-27T06:20:00Z",
        }, meta("policy", "governance_kernel", "gk-1")
    )
    runtime.service.issue_grant(
        {
            "schemaVersion": "1.0.0", "grantId": "g-toolbridge-live",
            "subject": {"actorId": "tool-broker", "kind": "execution_plane"},
            "capabilityId": "cap.file.read", "operations": ["file.read"],
            "scope": {"kind": "filesystem", "rootPath": str(root), "recursive": True},
            "policyDecisionId": "pd-toolbridge-live", "policyBundleDigest": digest,
            "conditions": [], "maxUses": 8, "validFrom": "2026-08-01T00:00:00Z",
            "validUntil": "2030-01-01T00:00:00Z",
            "issuedBy": {"actorId": "gk-1", "kind": "governance_kernel"}, "issuedAt": "2026-08-27T06:20:00Z",
        }, meta("grant", "governance_kernel", "gk-1")
    )
    runtime.service.activate_lease(
        {
            "schemaVersion": "1.0.0", "leaseId": "l-toolbridge-live", "grantId": "g-toolbridge-live",
            "missionId": "m-toolbridge-live", "taskId": "t-toolbridge-live",
            "executionContextId": "ec-toolbridge-live", "operations": ["file.read"],
            "scope": {"kind": "filesystem", "rootPath": str(root), "recursive": True},
            "maxUses": 8, "validFrom": "2026-08-01T00:00:00Z", "validUntil": "2030-01-01T00:00:00Z",
            "activatedAt": "2026-08-27T06:20:00Z",
        }, meta("lease", "governance_kernel", "gk-1")
    )
    return "g-toolbridge-live", "l-toolbridge-live"


def test_runtime_executor_creates_real_tool_execution_over_ipc(tmp_path: Path) -> None:
    import os
    import socket
    import subprocess
    import sys
    import time
    from capt_runtime.composition import create_runtime
    from capt_runtime.tool_broker import ToolBroker
    from desktop.desktop_runtime_client import RuntimeClient
    from capt_runtime.hermes_toolbridge import execute_via_runtime

    repo = Path(__file__).resolve().parents[2]
    ledger, sock, token = tmp_path / "runtime.db", tmp_path / "runtime.sock", tmp_path / "runtime.token"
    target = tmp_path / "README.md"
    target.write_text("CAPT_BRIDGE_LIVE_OK\n")
    runtime = create_runtime(str(ledger))
    grant, lease = _seed_read_authority(runtime, tmp_path)
    runtime.close()
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo)
    proc = subprocess.Popen(
        [sys.executable, str(repo / "desktop" / "capt_runtime_service.py"),
         "--ledger", str(ledger), "--sock", str(sock), "--token-file", str(token)],
        cwd=str(repo), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        deadline = time.time() + 10
        while time.time() < deadline:
            if sock.exists() and token.exists():
                try:
                    probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    probe.connect(str(sock)); probe.close(); break
                except OSError:
                    pass
            time.sleep(0.05)
        binding = ToolBridgeBinding(grant, lease, str(tmp_path), str(sock), str(token))
        request = binding.build_tool_request(
            "capt_read_file", {"path": "README.md"},
            request_id="live-1", requested_at="2026-08-27T06:21:00Z",
        )
        receipt = execute_via_runtime(binding, request)
        assert receipt["status"] == "accepted"
        result = receipt["result"]
        content = next(x["value"] for x in result["result"]["output"] if x["name"] == "content")
        assert content == "CAPT_BRIDGE_LIVE_OK\n"
        client = RuntimeClient(str(sock), str(token)); client.connect()
        state = client.get_state("tool_execution-" + result["toolExecutionId"])
        client.disconnect()
        assert state["state"] == "completed"
        assert state["operation"] == "file.read"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill(); proc.wait(timeout=3)


def test_stdio_server_emits_one_jsonrpc_response_per_request(tmp_path: Path) -> None:
    import io
    from capt_runtime.hermes_toolbridge import serve_stdio

    binding = ToolBridgeBinding("g-stdio", "l-stdio", str(tmp_path), "/tmp/sock", "/tmp/token")
    incoming = io.StringIO(
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}) + "\n" +
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}) + "\n" +
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}) + "\n"
    )
    outgoing = io.StringIO()
    serve_stdio(binding, lambda _: {"status": "accepted"}, input_stream=incoming, output_stream=outgoing)
    lines = [json.loads(line) for line in outgoing.getvalue().splitlines() if line.strip()]
    assert [line["id"] for line in lines] == [1, 2]
    assert lines[0]["result"]["serverInfo"]["name"] == "capt-toolbridge"
    assert len(lines[1]["result"]["tools"]) == 5


def test_bridge_module_subprocess_reads_through_live_runtime(tmp_path: Path) -> None:
    import os, socket, subprocess, sys, time
    from capt_runtime.composition import create_runtime

    repo = Path(__file__).resolve().parents[2]
    ledger, sock, token = tmp_path / "rt.db", tmp_path / "rt.sock", tmp_path / "rt.token"
    (tmp_path / "sample.txt").write_text("BRIDGE_SUBPROCESS_OK\n")
    runtime = create_runtime(str(ledger))
    grant, lease = _seed_read_authority(runtime, tmp_path)
    runtime.close()
    env = dict(os.environ); env["PYTHONPATH"] = str(repo)
    service = subprocess.Popen(
        [sys.executable, str(repo / "desktop" / "capt_runtime_service.py"), "--ledger", str(ledger),
         "--sock", str(sock), "--token-file", str(token)], cwd=str(repo), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        deadline = time.time() + 10
        while time.time() < deadline:
            if sock.exists() and token.exists():
                try:
                    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.connect(str(sock)); s.close(); break
                except OSError: pass
            time.sleep(0.05)
        bridge = subprocess.Popen(
            [sys.executable, "-m", "capt_runtime.hermes_toolbridge", "serve", "--sock", str(sock),
             "--token-file", str(token), "--grant-id", grant, "--lease-id", lease,
             "--filesystem-scope", str(tmp_path)], cwd=str(repo), env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "capt_read_file", "arguments": {"path": "sample.txt"}}},
        ]
        payload = "".join(json.dumps(item) + "\n" for item in requests)
        stdout, stderr = bridge.communicate(payload, timeout=10)
        assert bridge.returncode == 0, stderr
        responses = [json.loads(line) for line in stdout.splitlines() if line.strip()]
        assert [response["id"] for response in responses] == [1, 2]
        assert responses[1]["result"]["isError"] is False
        assert "BRIDGE_SUBPROCESS_OK" in responses[1]["result"]["content"][0]["text"]
    finally:
        service.terminate()
        try:
            service.wait(timeout=3)
        except subprocess.TimeoutExpired:
            service.kill(); service.wait(timeout=3)
