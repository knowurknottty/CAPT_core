from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone

from capt_runtime.node.authority import sign_capability
from capt_runtime.node.client import NodeClient
from capt_runtime.node.identity import (
    CapabilityAuthorityIdentity,
    ControllerIdentity,
    NodeIdentity,
)
from capt_runtime.node.journal import NodeOperationJournal
from capt_runtime.node.pairing import PairingRecord
from capt_runtime.node.server import NodeServer
from capt_runtime.node.types import NodeOperationRequest, OperationCapability

NOW = datetime(2026, 9, 8, 21, 0, tzinfo=timezone.utc)


def _active_pair(node, controller):
    pending = PairingRecord.pending(node, controller)
    return pending.activate(pending.short_code)


def _request(root, authority, operation_id: str, argv: list[str]):
    cap = OperationCapability(
        capability_id=f"cap-{operation_id}",
        bot_id="bot-1",
        mission_id="mission-1",
        task_id="task-1",
        controller_id="controller-1",
        node_id="node-1",
        permitted_operations=frozenset({"shell.exec"}),
        filesystem_roots=(str(root),),
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=10),
    )
    cap = sign_capability(cap, authority)
    return NodeOperationRequest(
        operation_id=operation_id,
        capability=cap,
        operation="shell.exec",
        arguments={"argv": argv, "cwd": str(root), "timeout_ms": 20_000},
        issued_at=NOW,
    )


def test_large_evidence_spools_survives_restart_and_is_chunk_readable(tmp_path):
    node = NodeIdentity.generate("node-1", "captain-mbp")
    controller = ControllerIdentity.generate("controller-1", "capt-runtime")
    authority = CapabilityAuthorityIdentity.generate("authority-1")
    journal = NodeOperationJournal(tmp_path / "journal.sqlite")
    pairing = _active_pair(node, controller)
    socket_path = tmp_path / "node.sock"
    request = _request(
        tmp_path,
        authority,
        "op-large",
        ["python3", "-c", "import sys; sys.stdout.write('x'*(1100*1024))"],
    )
    server = NodeServer(
        socket_path,
        node,
        journal,
        pairings=[pairing],
        authority_issuers={"authority-1": authority.public_key_bytes()},
        now=lambda: NOW,
    )
    server.start()
    try:
        client = NodeClient(socket_path, controller)
        result = client.execute(request)
        assert result["state"] == "closed"
        process = result["evidence"][0]
        assert "stdout" not in process
        assert process["stdoutStorage"] == "local_spool"
        assert process["stdoutRef"].startswith("node-evidence://")
        assert process["stdoutSha256"].startswith("sha256:")
        assert process["stdoutCapturedBytes"] == 1024 * 1024
        assert process["stdoutTotalBytes"] == 1100 * 1024
        assert process["stdoutTruncated"] is True
        first_ref = process["stdoutRef"]
    finally:
        server.close()
    restarted = NodeServer(
        socket_path,
        node,
        journal,
        pairings=[pairing],
        authority_issuers={"authority-1": authority.public_key_bytes()},
        now=lambda: NOW,
    )
    restarted.start()
    try:
        client = NodeClient(socket_path, controller)
        status = client.status("op-large")
        assert status["state"] == "closed"
        assert status["evidence"][0]["stdoutRef"] == first_ref
        chunk = client.read_evidence("op-large", first_ref, offset=0, limit=4096)
        assert chunk["eof"] is False
        assert chunk["offset"] == 0
        assert chunk["nextOffset"] == 4096
        assert base64.b64decode(chunk["dataBase64"]) == b"x" * 4096
        small = client.execute(
            _request(tmp_path, authority, "op-after-large", ["printf", "still-alive"])
        )
        assert small["evidence"][0]["stdout"] == "still-alive"
    finally:
        restarted.close()
        journal.close()
