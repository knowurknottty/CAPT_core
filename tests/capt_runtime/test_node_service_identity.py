"""R0.4 service-identity mode: policy parsing, scope ceiling, peer gate, durable denials.

Real-uid behaviour (a separate service account that cannot read the human credential)
is proven in test_node_service_identity_e2e.py with real Unix users.
"""
from __future__ import annotations

import json
import socket
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from capt_runtime.node import server as server_mod
from capt_runtime.node import service
from capt_runtime.node.authority import sign_capability
from capt_runtime.node.client import NodeClient
from capt_runtime.node.identity import CapabilityAuthorityIdentity, ControllerIdentity, NodeIdentity
from capt_runtime.node.journal import NodeOperationJournal
from capt_runtime.node.pairing import PairingRecord
from capt_runtime.node.server import NodeServer
from capt_runtime.node.service import (
    DenialLog,
    ServiceIdentityPolicy,
    ServicePreflightError,
    require_scope_within_service,
)
from capt_runtime.node.types import NodeOperationRequest, OperationCapability


def _block(tmp_path: Path, **over):
    block = {
        "trustDir": str(tmp_path / "trust"),
        "stateDir": str(tmp_path / "state"),
        "allowedPeerUids": [501],
        "forbiddenUids": [501],
        "forbiddenReadablePaths": [str(tmp_path / "human.token")],
        "socketGroup": None,
    }
    block.update(over)
    return {"serviceIdentity": block}


def test_absent_block_keeps_legacy_mode() -> None:
    assert ServiceIdentityPolicy.from_config({"endpoint": "unix:///x"}) is None


@pytest.mark.parametrize("override,code", [
    ({"trustDir": "relative/trust"}, "node_service_identity_trustDir_must_be_absolute"),
    ({"allowedPeerUids": []}, "node_service_identity_allowedPeerUids_required"),
    ({"forbiddenUids": [True]}, "node_service_identity_forbiddenUids_invalid"),
    ({"forbiddenReadablePaths": ["relative"]}, "node_service_identity_forbiddenReadablePaths_invalid"),
    ({"socketGroup": ""}, "node_service_identity_socketGroup_invalid"),
])
def test_policy_rejects_malformed_blocks(tmp_path: Path, override, code) -> None:
    with pytest.raises(ValueError, match=code):
        ServiceIdentityPolicy.from_config(_block(tmp_path, **override))


def test_preflight_refuses_root_and_forbidden_uids(tmp_path: Path, monkeypatch) -> None:
    policy = ServiceIdentityPolicy.from_config(_block(tmp_path))
    kwargs = dict(config_path=tmp_path / "node.json", workspace_roots=[str(tmp_path / "ws")],
                  code_root=tmp_path / "app", legacy_state_dir=tmp_path / ".capt-node-state")
    monkeypatch.setattr(service.os, "geteuid", lambda: 0)
    with pytest.raises(ServicePreflightError) as exc:
        service.preflight(policy, **kwargs)
    assert exc.value.code == "NODE_REFUSES_ROOT"
    monkeypatch.setattr(service.os, "geteuid", lambda: 501)
    with pytest.raises(ServicePreflightError) as exc:
        service.preflight(policy, **kwargs)
    assert exc.value.code == "NODE_RUNNING_AS_FORBIDDEN_UID"


def test_capability_roots_may_narrow_but_never_widen(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    (ws / "sub").mkdir(parents=True)
    require_scope_within_service([str(ws / "sub")], [str(ws)])
    for widened in (str(tmp_path), "/", str(ws) + "/../" + "elsewhere"):
        with pytest.raises(PermissionError, match="NODE_CAPABILITY_ROOT_OUTSIDE_SERVICE_SCOPE"):
            require_scope_within_service([widened], [str(ws)])


def test_denial_log_appends_durable_json_lines(tmp_path: Path) -> None:
    log = DenialLog(tmp_path / "denials.jsonl")
    log.record("NODE_PEER_UID_DENIED", peerUid=502, kind=None)
    log.record("signature_invalid", controllerId="c", operationId="op-1")
    lines = [json.loads(x) for x in (tmp_path / "denials.jsonl").read_text().splitlines()]
    assert [x["code"] for x in lines] == ["NODE_PEER_UID_DENIED", "signature_invalid"]
    assert "kind" not in lines[0] and lines[1]["operationId"] == "op-1"
    assert (tmp_path / "denials.jsonl").stat().st_mode & 0o777 == 0o640


# ---------------------------------------------------------------- live server, faked peer uid

def _served(tmp_path: Path, monkeypatch, peer: int):
    ws = tmp_path / "ws"
    ws.mkdir()
    node = NodeIdentity.generate("node-t", "t")
    controller = ControllerIdentity.generate("ctl", "t")
    authority = CapabilityAuthorityIdentity.generate("authority-t")
    pairing = PairingRecord.pending(node, controller)
    pairing = pairing.activate(pairing.short_code)
    policy = ServiceIdentityPolicy.from_config(_block(tmp_path, allowedPeerUids=[501], forbiddenUids=[501]))
    monkeypatch.setattr(server_mod, "peer_uid", lambda conn: peer)
    journal = NodeOperationJournal(tmp_path / "journal.sqlite")
    sock = tmp_path / "n.sock"
    srv = NodeServer(sock, node, journal, pairings=[pairing],
                     authority_issuers={"authority-t": authority.public_key_bytes()},
                     now=lambda: datetime.now(timezone.utc), service_policy=policy,
                     service_roots=(str(ws),), denial_log=DenialLog(tmp_path / "denials.jsonl"))
    srv.start()
    return srv, NodeClient(sock, controller), authority, controller, ws


def _request(authority, controller, roots, op_id="op-1", cwd=None):
    now = datetime.now(timezone.utc)
    cap = sign_capability(OperationCapability(
        capability_id="cap-1", bot_id="b", mission_id="m", task_id="t", controller_id=controller.controller_id,
        node_id="node-t", permitted_operations=frozenset({"shell.exec"}), filesystem_roots=tuple(roots),
        issued_at=now, expires_at=now + timedelta(minutes=5)), authority)
    return NodeOperationRequest(operation_id=op_id, capability=cap, operation="shell.exec",
                                arguments={"argv": ["/bin/echo", "ok"], "cwd": cwd or roots[0], "timeout_ms": 5000},
                                issued_at=now)


def test_socket_mode_and_peer_gate(tmp_path: Path, monkeypatch) -> None:
    srv, client, authority, controller, ws = _served(tmp_path, monkeypatch, peer=502)
    try:
        assert (tmp_path / "n.sock").stat().st_mode & 0o777 == 0o660
        with pytest.raises(Exception, match="NODE_PEER_UID_DENIED"):
            client.execute(_request(authority, controller, [str(ws)]))
        entry = json.loads((tmp_path / "denials.jsonl").read_text().splitlines()[0])
        assert entry["code"] == "NODE_PEER_UID_DENIED" and entry["peerUid"] == 502
    finally:
        srv.close()


def test_allowed_peer_executes_and_widened_capability_is_refused(tmp_path: Path, monkeypatch) -> None:
    srv, client, authority, controller, ws = _served(tmp_path, monkeypatch, peer=501)
    try:
        ok = client.execute(_request(authority, controller, [str(ws)], op_id="op-ok"))
        assert ok["state"] == "closed" and ok["exitCode"] == 0
        # A validly signed capability that names a root the service was not deployed with.
        with pytest.raises(Exception, match="NODE_CAPABILITY_ROOT_OUTSIDE_SERVICE_SCOPE"):
            client.execute(_request(authority, controller, [str(tmp_path)], op_id="op-wide", cwd=str(ws)))
        codes = [json.loads(x)["code"] for x in (tmp_path / "denials.jsonl").read_text().splitlines()]
        assert codes == ["NODE_CAPABILITY_ROOT_OUTSIDE_SERVICE_SCOPE"]
    finally:
        srv.close()
