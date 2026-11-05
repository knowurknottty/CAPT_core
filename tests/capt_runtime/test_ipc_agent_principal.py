"""Execute-only agent principal at the RuntimeService IPC boundary.

These tests start a real RuntimeService process and talk to it over its Unix
socket, so the boundary under test is the one an external agent host would hit.
"""
from __future__ import annotations

import json
import os
import secrets
import socket
import stat
import struct
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from capt_runtime.tool_broker import TOOL_REQUEST_COMMITMENT_KIND, tool_request_fingerprint
from desktop.ipc_principal import (
    AGENT_PRINCIPAL_COMMAND_OPS,
    AGENT_PRINCIPAL_OP_DENIED,
    match_principal,
    write_secret_file,
)

REPO = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- client

class Conn:
    def __init__(self, sock_path: Path, token: str) -> None:
        self.s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.s.settimeout(20)
        self.s.connect(str(sock_path))
        self._send({"token": token})
        self.auth = self._recv()

    def _send(self, obj: dict) -> None:
        blob = json.dumps(obj).encode()
        self.s.sendall(struct.pack(">I", len(blob)) + blob)

    def _recv(self) -> dict:
        def exact(n: int) -> bytes:
            buf = b""
            while len(buf) < n:
                chunk = self.s.recv(n - len(buf))
                if not chunk:
                    raise ConnectionError("closed")
                buf += chunk
            return buf
        (n,) = struct.unpack(">I", exact(4))
        return json.loads(exact(n))

    def query(self, op: str, **fields) -> dict:
        self._send({"op": op, **fields})
        return self._recv()

    def command(self, op: str, payload: dict, idem: str | None = None) -> dict:
        self._send({"op": "command", "command": {
            "commandId": "cmd-" + secrets.token_hex(6),
            "operatorId": self.auth["operatorId"],
            "sessionId": self.auth["sessionId"],
            "schemaVersion": "1.0.0",
            "correlationId": "corr-" + secrets.token_hex(4),
            "idempotencyKey": idem or ("idem-" + secrets.token_hex(6)),
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "op": op,
            "payload": payload,
        }})
        return self._recv()

    def close(self) -> None:
        self.s.close()


@pytest.fixture()
def runtime(tmp_path: Path):
    # AF_UNIX paths are short on macOS; keep the state root shallow.
    root = Path(os.environ.get("TMPDIR", "/tmp")) / ("capt-ap-" + secrets.token_hex(4))
    root.mkdir(mode=0o700)
    paths = {
        "root": root,
        "ledger": root / "rt.db",
        "sock": root / "rt.sock",
        "human": root / "runtime.token",
        "agent": root / "runtime.agent.token",
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "desktop.capt_runtime_service",
         "--ledger", str(paths["ledger"]), "--sock", str(paths["sock"]),
         "--token-file", str(paths["human"]), "--agent-token-file", str(paths["agent"])],
        cwd=str(REPO), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    deadline = time.monotonic() + 30
    while not (paths["sock"].exists() and paths["agent"].exists()):
        if proc.poll() is not None:
            raise AssertionError(proc.stdout.read().decode()[-3000:])
        if time.monotonic() > deadline:
            proc.kill()
            raise AssertionError("runtime did not start")
        time.sleep(0.05)
    try:
        yield paths
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def _human(p) -> Conn:
    return Conn(p["sock"], p["human"].read_text().strip())


def _agent(p) -> Conn:
    return Conn(p["sock"], p["agent"].read_text().strip())


# --------------------------------------------------------------------------- intents

def _file_write_request(root: Path, name: str, content: str, *, request_id: str, ctx: str, idem: str) -> dict:
    import hashlib
    grant = "g-human-approved-" + hashlib.sha256(request_id.encode()).hexdigest()[:24]
    lease = "l-human-approved-" + hashlib.sha256((request_id + ":" + ctx).encode()).hexdigest()[:24]
    request = {
        "schemaVersion": "1.0.0",
        "toolRequestId": "req-" + idem,
        "toolId": "file.operations",
        "operation": "file.write",
        "arguments": [
            {"kind": "path", "name": "path", "value": str(root / name)},
            {"kind": "string", "name": "content", "value": content},
        ],
        "consequential": True,
        "grantId": grant,
        "leaseId": lease,
        "reservationId": None,
        "backendId": "local",
        "targetIdentity": str(root / name),
        "filesystemScope": str(root),
        "idempotencyKey": idem,
        "operationFingerprint": "sha256:" + "0" * 64,
        "replayPolicy": "never",
        "requestedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    request["operationFingerprint"] = tool_request_fingerprint(request)
    return request


def _intent(root: Path, request_id: str, commitment: str | None) -> dict:
    # ToolBroker requests recursive filesystem scope for file tools
    # (tool_broker._scope_for), so the approved scope must be recursive; the
    # tool-request commitment still pins the exact path and bytes.
    scope = {"kind": "filesystem", "rootPath": str(root), "recursive": True}
    expires = (datetime.now(timezone.utc) + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    mission = "m-" + request_id
    intent = {
        "schemaVersion": "1.0.0", "missionId": mission, "taskId": mission + "-t1",
        "requestId": request_id,
        "objective": "Write one approved file.", "rawRequest": "write one approved file",
        "normalizedRequest": "write one approved file", "scope": scope, "constraints": [],
        "successCriteria": [{"criterionId": "sc-1", "statement": "file written", "requiresVerification": True}],
        "terminationCriteria": [], "unresolvedAmbiguities": [], "requiresApproval": True,
        "requestedCapability": "cap.file.write", "operations": ["file.write"], "consequential": True,
        "capabilitySubject": {"actorId": "tool-broker", "kind": "execution_plane"},
        "capabilityConditions": [], "capabilityMaxUses": 1, "maxAttempts": 1,
        "resource": str(root), "operation": "GovernedFileWrite", "riskClassification": "consequential",
        "policyReason": "Approve exactly one file.write inside the scope.",
        "expiresAt": expires, "remainingUses": 1,
        "externalCommitments": [],
    }
    if commitment is not None:
        intent["externalCommitments"] = [
            {"kind": TOOL_REQUEST_COMMITMENT_KIND, "digest": commitment, "reference": request_id}
        ]
    return intent


def _approve_and_activate(human: Conn, intent: dict, ctx: str) -> None:
    created = human.command("create_mission", intent)
    assert created["status"] == "accepted", created
    decided = human.command("submit_approval_decision", {"requestId": intent["requestId"], "decision": "approve"})
    assert decided["status"] == "accepted", decided
    activated = human.command("activate_approved_capability",
                              {"requestId": intent["requestId"], "executionContextId": ctx})
    assert activated["status"] == "accepted", activated


# --------------------------------------------------------------------------- tests

def test_match_principal_is_exact_and_typed() -> None:
    assert match_principal("h" * 64, "h" * 64, "a" * 64) == "human"
    assert match_principal("a" * 64, "h" * 64, "a" * 64) == "agent"
    assert match_principal("a" * 64, "h" * 64, None) is None
    assert match_principal(None, "h" * 64, "a" * 64) is None
    assert match_principal(["h" * 64], "h" * 64, "a" * 64) is None
    assert AGENT_PRINCIPAL_COMMAND_OPS == frozenset({"run_tool"})


def test_write_secret_file_never_world_accessible(tmp_path: Path) -> None:
    target = tmp_path / "tok"
    assert write_secret_file(target, "v1", mode=0o600) == "v1"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert write_secret_file(target, "v2", mode=0o600) == "v2"  # replace in place
    with pytest.raises(ValueError):
        write_secret_file(tmp_path / "bad", "x", mode=0o644)
    assert not [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")]  # no leaked temporaries


def test_token_files_and_principal_reporting(runtime) -> None:
    for key in ("human", "agent"):
        mode = stat.S_IMODE(runtime[key].stat().st_mode)
        assert mode == 0o600, (key, oct(mode))
    assert runtime["human"].read_text() != runtime["agent"].read_text()
    human, agent = _human(runtime), _agent(runtime)
    try:
        assert human.auth["principal"] == "human"
        assert agent.auth["principal"] == "agent"
        assert agent.auth["sessionId"].startswith("sess-agent-")
        assert "tool_request_commitment.v1" in agent.auth["features"]
        assert agent.query("identity")["ok"] is True  # reads stay available
    finally:
        human.close()
        agent.close()


@pytest.mark.parametrize("op", [
    "submit_approval_decision", "create_mission", "activate_approved_capability",
    "shutdown", "install_managed_skill", "update_memory_trigger_policy",
    # intercepted by command-service subclasses before the base class runs:
    "create_replay_fork", "revoke_capability", "steer_deliberation",
])
def test_agent_principal_refused_for_every_non_run_tool_op(runtime, op) -> None:
    agent = _agent(runtime)
    try:
        receipt = agent.command(op, {})
        assert receipt["status"] == "rejected"
        assert receipt["classification"] == "unauthorized"
        assert receipt["error"]["code"] == AGENT_PRINCIPAL_OP_DENIED
        rejections = agent.query("security_rejections")
        kinds = json.dumps(rejections)
        assert "agent_principal_op_denied" in kinds
    finally:
        agent.close()


def test_agent_cannot_decide_a_pending_approval(runtime, tmp_path: Path) -> None:
    root = tmp_path / "work"
    root.mkdir()
    human, agent = _human(runtime), _agent(runtime)
    try:
        intent = _intent(root, "approval-ap-" + secrets.token_hex(4), None)
        assert human.command("create_mission", intent)["status"] == "accepted"
        refused = agent.command("submit_approval_decision",
                                {"requestId": intent["requestId"], "decision": "approve"})
        assert refused["error"]["code"] == AGENT_PRINCIPAL_OP_DENIED
        state = human.query("get_state", streamId="human_approval-" + intent["requestId"])["result"]
        assert state["state"] == "requested"
    finally:
        human.close()
        agent.close()


def test_agent_spends_only_the_exact_committed_request(runtime, tmp_path: Path) -> None:
    root = tmp_path / "protected"
    root.mkdir()
    request_id = "approval-ap-" + secrets.token_hex(4)
    ctx = "execctx-" + request_id
    approved = _file_write_request(root, "out.txt", "approved bytes\n",
                                   request_id=request_id, ctx=ctx, idem="ia-fw-" + request_id)
    human, agent = _human(runtime), _agent(runtime)
    try:
        _approve_and_activate(human, _intent(root, request_id, approved["operationFingerprint"]), ctx)

        mutated = _file_write_request(root, "out.txt", "MUTATED\n",
                                      request_id=request_id, ctx=ctx, idem="ia-fw-mut-" + request_id)
        denied = agent.command("run_tool", mutated, idem=mutated["idempotencyKey"])
        assert denied["status"] == "accepted"  # the command was processed ...
        assert denied["result"]["status"] == "denied"  # ... and the effect refused
        assert "TOOL_REQUEST_COMMITMENT_MISMATCH" in json.dumps(denied["result"])
        assert not (root / "out.txt").exists()

        ok = agent.command("run_tool", approved, idem=approved["idempotencyKey"])
        assert ok["result"]["status"] == "succeeded", ok
        assert (root / "out.txt").read_text() == "approved bytes\n"

        again = _file_write_request(root, "out.txt", "approved bytes\n",
                                    request_id=request_id, ctx=ctx, idem="ia-fw-again-" + request_id)
        second = agent.command("run_tool", again, idem=again["idempotencyKey"])
        assert second["result"]["status"] == "denied"  # different key => different fingerprint
    finally:
        human.close()
        agent.close()


def test_uncommitted_grant_behaviour_is_unchanged(runtime, tmp_path: Path) -> None:
    root = tmp_path / "plain"
    root.mkdir()
    request_id = "approval-ap-" + secrets.token_hex(4)
    ctx = "execctx-" + request_id
    human, agent = _human(runtime), _agent(runtime)
    try:
        _approve_and_activate(human, _intent(root, request_id, None), ctx)
        req = _file_write_request(root, "any.txt", "any bytes\n",
                                  request_id=request_id, ctx=ctx, idem="ia-fw-" + request_id)
        ok = agent.command("run_tool", req, idem=req["idempotencyKey"])
        assert ok["result"]["status"] == "succeeded", ok
    finally:
        human.close()
        agent.close()


def test_agent_token_rejected_when_principal_not_configured(tmp_path: Path) -> None:
    root = Path(os.environ.get("TMPDIR", "/tmp")) / ("capt-ap-" + secrets.token_hex(4))
    root.mkdir(mode=0o700)
    sock, tok = root / "rt.sock", root / "runtime.token"
    proc = subprocess.Popen(
        [sys.executable, "-m", "desktop.capt_runtime_service",
         "--ledger", str(root / "rt.db"), "--sock", str(sock), "--token-file", str(tok)],
        cwd=str(REPO), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    try:
        deadline = time.monotonic() + 30
        while not sock.exists():
            assert proc.poll() is None and time.monotonic() < deadline
            time.sleep(0.05)
        human = Conn(sock, tok.read_text().strip())
        assert human.auth["principal"] == "human"
        human.close()
        stranger = Conn(sock, "a" * 64)
        assert stranger.auth == {"ok": False, "error": "unauthenticated"}
        stranger.close()
    finally:
        proc.terminate()
        proc.wait(timeout=10)
