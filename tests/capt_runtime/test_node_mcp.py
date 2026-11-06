from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from capt_runtime.node.authority import sign_capability
from capt_runtime.node.identity import CapabilityAuthorityIdentity
from capt_runtime.node.mcp_server import NodeMCPServer
from capt_runtime.node.types import OperationCapability

NOW = datetime(2026, 9, 8, 21, 30, tzinfo=timezone.utc)


class FakeNodeClient:
    def __init__(self) -> None:
        self.requests = []
        self.status_ids = []
        self.evidence_reads = []

    def execute(self, request):
        self.requests.append(request)
        return {
            "operationId": request.operation_id,
            "state": "closed",
            "exitCode": 0,
            "requestDigest": "sha256:" + "1" * 64,
            "evidence": [{"kind": "process", "stdout": "ok", "stderr": ""}],
            "replayed": False,
        }

    def status(self, operation_id):
        self.status_ids.append(operation_id)
        return {"operationId": operation_id, "state": "closed"}

    def read_evidence(self, operation_id, ref, *, offset=0, limit=64 * 1024):
        self.evidence_reads.append((operation_id, ref, offset, limit))
        return {
            "operationId": operation_id,
            "ref": ref,
            "offset": offset,
            "nextOffset": offset + 4,
            "totalBytes": 4,
            "dataBase64": "dGVzdA==",
            "eof": True,
        }


def _capability(root: Path, *, expired: bool = False) -> OperationCapability:
    authority = CapabilityAuthorityIdentity.generate("authority-mcp")
    expires = NOW - timedelta(seconds=1) if expired else NOW + timedelta(hours=1)
    return sign_capability(
        OperationCapability(
            capability_id="cap-mcp-1",
            bot_id="bot-mcp",
            mission_id="mission-mcp",
            task_id="task-mcp",
            controller_id="controller-mcp",
            node_id="node-mcp",
            permitted_operations=frozenset({"shell.exec"}),
            filesystem_roots=(str(root),),
            issued_at=NOW - timedelta(minutes=1),
            expires_at=expires,
        ),
        authority,
    )


def test_mcp_surface_has_no_authority_grant_tool(tmp_path: Path):
    server = NodeMCPServer(FakeNodeClient(), _capability(tmp_path), now=lambda: NOW)
    names = {tool["name"] for tool in server.list_tools()}
    assert names == {
        "node_exec", "node_status", "node_evidence_read", "node_capability_info"
    }
    assert not {name for name in names if "grant" in name or "authorize" in name}


def test_mcp_exec_reuses_presigned_capability_and_enforces_scope(tmp_path: Path):
    client = FakeNodeClient()
    capability = _capability(tmp_path)
    server = NodeMCPServer(client, capability, now=lambda: NOW)
    result = server.call_tool(
        "node_exec",
        {
            "operationId": "op-mcp-1",
            "cwd": str(tmp_path),
            "argv": ["printf", "ok"],
            "timeoutMs": 2500,
        },
    )
    assert result["state"] == "closed"
    request = client.requests[0]
    assert request.capability == capability
    assert request.arguments["timeout_ms"] == 2500
    with pytest.raises(PermissionError, match="mcp_cwd_outside_capability_scope"):
        server.call_tool(
            "node_exec",
            {"operationId": "op-mcp-escape", "cwd": str(tmp_path.parent), "argv": ["pwd"]},
        )


def test_mcp_expired_capability_blocks_before_dispatch(tmp_path: Path):
    client = FakeNodeClient()
    server = NodeMCPServer(client, _capability(tmp_path, expired=True), now=lambda: NOW)
    with pytest.raises(PermissionError, match="capability_expired"):
        server.call_tool(
            "node_exec",
            {"operationId": "op-expired", "cwd": str(tmp_path), "argv": ["pwd"]},
        )
    assert client.requests == []


def test_mcp_evidence_read_is_bounded_and_controller_scoped(tmp_path: Path):
    client = FakeNodeClient()
    server = NodeMCPServer(client, _capability(tmp_path), now=lambda: NOW)
    result = server.call_tool(
        "node_evidence_read",
        {
            "operationId": "op-large",
            "ref": "node-evidence://" + "a" * 64,
            "offset": 16,
            "limit": 4096,
        },
    )
    assert result["eof"] is True
    assert client.evidence_reads == [
        ("op-large", "node-evidence://" + "a" * 64, 16, 4096)
    ]
    with pytest.raises(ValueError, match="mcp_evidence_limit_out_of_range"):
        server.call_tool(
            "node_evidence_read",
            {"operationId": "op-large", "ref": "node-evidence://x", "limit": 65537},
        )


def test_mcp_unknown_tool_is_specific(tmp_path: Path):
    server = NodeMCPServer(FakeNodeClient(), _capability(tmp_path), now=lambda: NOW)
    with pytest.raises(ValueError, match="mcp_tool_not_supported:nope"):
        server.call_tool("nope", {})


def test_mcp_stdio_executes_through_node_with_presigned_capability(tmp_path: Path):
    import base64
    import sys

    from capt_runtime.mcp import MCPStdioClient
    from capt_runtime.node.cli import (
        _load_node,
        _load_pairings,
        _socket_path,
        _state_dir,
        authorize_mcp_capability,
        init_config,
        load_config,
        pair_controller,
    )
    from capt_runtime.node.journal import NodeOperationJournal
    from capt_runtime.node.server import NodeServer

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config_path = tmp_path / "node.json"
    init_config(config_path, workspace_roots=[str(workspace)])
    pending = pair_controller(config_path, "controller-mcp-live")
    pair_controller(
        config_path,
        "controller-mcp-live",
        approve_code=str(pending["verificationCode"]),
    )
    capability_path = tmp_path / "mcp-capability.json"
    authorize_mcp_capability(
        config_path,
        "controller-mcp-live",
        capability_path,
        expires_minutes=30,
    )
    config = load_config(config_path)
    journal = NodeOperationJournal(tmp_path / "journal.sqlite")
    authority_public = base64.b64decode(
        (_state_dir(config_path) / "authority.pub").read_text().strip(), validate=True
    )
    node_server = NodeServer(
        _socket_path(config),
        _load_node(config_path, config),
        journal,
        pairings=_load_pairings(config_path),
        authority_issuers={config.authority_id: authority_public},
        now=lambda: datetime.now(timezone.utc),
    )
    node_server.start()
    repo = Path(__file__).resolve().parents[2]
    client = MCPStdioClient(
        [
            sys.executable,
            "-m",
            "capt_runtime.node.mcp_stdio",
            "--config",
            str(config_path),
            "--controller-id",
            "controller-mcp-live",
            "--capability-file",
            str(capability_path),
        ],
        environment={"PYTHONPATH": str(repo)},
        timeout=10.0,
    )
    try:
        names = {tool["name"] for tool in client.list_tools()}
        assert names == {
            "node_exec", "node_status", "node_evidence_read", "node_capability_info"
        }
        result = client.call_tool(
            "node_exec",
            {
                "operationId": "op-mcp-live",
                "cwd": str(workspace),
                "argv": ["printf", "mcp-node-ok"],
            },
        )
        assert result["isError"] is False
        structured = result["structuredContent"]
        assert structured["state"] == "closed"
        process = next(item for item in structured["evidence"] if item["kind"] == "process")
        assert process["stdout"] == "mcp-node-ok"
    finally:
        client.close()
        node_server.close()
        journal.close()
