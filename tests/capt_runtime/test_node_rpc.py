from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

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


def _request(root, authority, operation_id="op-1"):
    cap = OperationCapability(
        capability_id="cap-1", bot_id="bot-1", mission_id="m-1", task_id="t-1",
        controller_id="controller-1", node_id="node-1",
        permitted_operations=frozenset({"shell.exec"}), filesystem_roots=(str(root),),
        issued_at=NOW, expires_at=NOW + timedelta(minutes=10),
    )
    cap = sign_capability(cap, authority)
    return NodeOperationRequest(
        operation_id=operation_id, capability=cap, operation="shell.exec",
        arguments={"argv": ["printf", "hello"], "cwd": str(root)}, issued_at=NOW,
    )


def _active_pair(node, controller):
    pending = PairingRecord.pending(node, controller)
    return pending.activate(pending.short_code)


def test_local_socket_exec_requires_active_pairing(tmp_path):
    node = NodeIdentity.generate("node-1", "captain-mbp")
    controller = ControllerIdentity.generate("controller-1", "capt-runtime")
    authority = CapabilityAuthorityIdentity.generate("authority-1")
    journal = NodeOperationJournal(tmp_path / "journal.sqlite")
    server = NodeServer(
        tmp_path / "node.sock", node, journal, pairings=[],
        authority_issuers={"authority-1": authority.public_key_bytes()}, now=lambda: NOW,
    )
    server.start()
    try:
        client = NodeClient(tmp_path / "node.sock", controller)
        with pytest.raises(PermissionError, match="controller_not_paired"):
            client.execute(_request(tmp_path, authority))
    finally:
        server.close()


def test_local_socket_exec_and_status_reconnect(tmp_path):
    node = NodeIdentity.generate("node-1", "captain-mbp")
    controller = ControllerIdentity.generate("controller-1", "capt-runtime")
    authority = CapabilityAuthorityIdentity.generate("authority-1")
    journal = NodeOperationJournal(tmp_path / "journal.sqlite")
    server = NodeServer(
        tmp_path / "node.sock", node, journal,
        pairings=[_active_pair(node, controller)],
        authority_issuers={"authority-1": authority.public_key_bytes()}, now=lambda: NOW,
    )
    server.start()
    try:
        first = NodeClient(tmp_path / "node.sock", controller).execute(_request(tmp_path, authority))
        assert first["state"] == "closed"
        status = NodeClient(tmp_path / "node.sock", controller).status("op-1")
        assert status["operationId"] == "op-1"
        assert status["state"] == "closed"
    finally:
        server.close()


def test_duplicate_operation_is_not_redispatched(tmp_path):
    node = NodeIdentity.generate("node-1", "captain-mbp")
    controller = ControllerIdentity.generate("controller-1", "capt-runtime")
    authority = CapabilityAuthorityIdentity.generate("authority-1")
    journal = NodeOperationJournal(tmp_path / "journal.sqlite")
    target = tmp_path / "count.txt"
    request = _request(tmp_path, authority, "op-dup")
    request = NodeOperationRequest(
        operation_id=request.operation_id,
        capability=request.capability,
        operation="shell.exec",
        arguments={
            "argv": ["python3", "-c", f"from pathlib import Path; p=Path({str(target)!r}); p.write_text(p.read_text()+'x' if p.exists() else 'x')"],
            "cwd": str(tmp_path),
        },
        issued_at=NOW,
    )
    server = NodeServer(
        tmp_path / "node.sock", node, journal,
        pairings=[_active_pair(node, controller)],
        authority_issuers={"authority-1": authority.public_key_bytes()}, now=lambda: NOW,
    )
    server.start()
    try:
        client = NodeClient(tmp_path / "node.sock", controller)
        client.execute(request)
        second = client.execute(request)
        assert second["replayed"] is True
        assert target.read_text() == "x"
    finally:
        server.close()


def test_malformed_frame_is_rejected_without_generic_error(tmp_path):
    from capt_runtime.node.protocol import decode_frame

    with pytest.raises(ValueError, match="frame_too_short"):
        decode_frame(b"{}")


def test_client_transport_timeout_tracks_bounded_operation_timeout(tmp_path):
    from capt_runtime.node.client import operation_transport_timeout

    authority = CapabilityAuthorityIdentity.generate("authority-timeout")
    request = _request(tmp_path, authority, "op-timeout-client")
    request = NodeOperationRequest(
        operation_id=request.operation_id,
        capability=request.capability,
        operation=request.operation,
        arguments={**request.arguments, "timeout_ms": 90_000},
        issued_at=request.issued_at,
    )
    assert operation_transport_timeout(request) == 95.0



def test_long_operation_does_not_block_status_or_unrelated_rpc(tmp_path):
    import threading
    import time

    node = NodeIdentity.generate("node-1", "captain-mbp")
    controller = ControllerIdentity.generate("controller-1", "capt-runtime")
    authority = CapabilityAuthorityIdentity.generate("authority-1")
    journal = NodeOperationJournal(tmp_path / "journal.sqlite")
    server = NodeServer(
        tmp_path / "node.sock", node, journal,
        pairings=[_active_pair(node, controller)],
        authority_issuers={"authority-1": authority.public_key_bytes()}, now=lambda: NOW,
    )
    server.start()

    long_request = _request(tmp_path, authority, "op-long")
    long_request = NodeOperationRequest(
        operation_id=long_request.operation_id,
        capability=long_request.capability,
        operation=long_request.operation,
        arguments={
            "argv": ["python3", "-c", "import time; time.sleep(2)"],
            "cwd": str(tmp_path),
            "timeout_ms": 5_000,
        },
        issued_at=long_request.issued_at,
    )
    outcome = {}

    def run_long():
        outcome["result"] = NodeClient(tmp_path / "node.sock", controller).execute(long_request)

    worker = threading.Thread(target=run_long)
    worker.start()
    try:
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            row = journal.lookup("op-long")
            if row and row["state"] == "executing":
                break
            time.sleep(0.01)
        else:
            raise AssertionError("long operation never entered executing state")

        status = NodeClient(tmp_path / "node.sock", controller).status("op-long")
        assert status["state"] == "executing"
        assert worker.is_alive()

        quick = NodeClient(tmp_path / "node.sock", controller).execute(
            _request(tmp_path, authority, "op-quick")
        )
        assert quick["state"] == "closed"
        assert worker.is_alive()
    finally:
        worker.join(timeout=5.0)
        server.close()
        journal.close()

    assert outcome["result"]["state"] == "closed"
