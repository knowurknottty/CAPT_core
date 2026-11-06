from __future__ import annotations

import argparse
import base64
import json
import os
import platform
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .authority import sign_capability
from .client import NodeClient
from .identity import CapabilityAuthorityIdentity, ControllerIdentity, NodeIdentity
from .journal import NodeOperationJournal
from .pairing import PairingRecord, PairingState
from .protocol import capability_to_wire
from .server import NodeServer
from .service import DenialLog, ServiceIdentityPolicy, ServicePreflightError, preflight
from .types import NodeOperationRequest, OperationCapability


def validate_endpoint(endpoint: str) -> str:
    if not endpoint.startswith("unix://") or len(endpoint) <= len("unix://"):
        raise ValueError("node_endpoint_must_be_local_unix_socket")
    return endpoint


@dataclass(frozen=True)
class NodeConfig:
    endpoint: str
    workspace_roots: tuple[str, ...]
    emergency_stop_hotkey: str | None = None
    node_id: str = "node-local"
    authority_id: str = "authority-local"
    device_name: str = "capt-node"

    def __post_init__(self) -> None:
        validate_endpoint(self.endpoint)
        if not self.workspace_roots:
            raise ValueError("node_workspace_roots_required")
        if any(not root or not Path(root).is_absolute() for root in self.workspace_roots):
            raise ValueError("node_workspace_root_must_be_absolute")

    def to_dict(self) -> dict[str, object]:
        return {
            "endpoint": self.endpoint,
            "workspaceRoots": list(self.workspace_roots),
            "emergencyStopHotkey": self.emergency_stop_hotkey,
            "nodeId": self.node_id,
            "authorityId": self.authority_id,
            "deviceName": self.device_name,
        }


def _state_dir(config_path: str | Path) -> Path:
    return Path(config_path).parent / ".capt-node-state"


def _write_secret(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, base64.b64encode(raw) + b"\n")
    finally:
        os.close(fd)
    os.chmod(path, 0o600)


def _read_secret(path: Path) -> bytes:
    return base64.b64decode(path.read_text().strip(), validate=True)


def init_config(path: str | Path, *, workspace_roots: list[str]) -> NodeConfig:
    target = Path(path)
    config = NodeConfig(
        endpoint=f"unix://{target.parent / 'capt-node.sock'}",
        workspace_roots=tuple(workspace_roots),
        emergency_stop_hotkey=None,
        node_id="node-" + uuid.uuid4().hex[:20],
        authority_id="authority-" + uuid.uuid4().hex[:20],
        device_name=platform.node() or "capt-node",
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(config.to_dict(), sort_keys=True, indent=2) + "\n")
    os.chmod(target, 0o600)
    state = _state_dir(target)
    node = NodeIdentity.generate(config.node_id, config.device_name)
    authority = CapabilityAuthorityIdentity.generate(config.authority_id)
    _write_secret(state / "node.key", node.private_key_bytes())
    _write_secret(state / "authority.key", authority.private_key_bytes())
    (state / "authority.pub").write_text(base64.b64encode(authority.public_key_bytes()).decode("ascii") + "\n")
    os.chmod(state / "authority.pub", 0o600)
    (state / "pairings.json").write_text("[]\n")
    os.chmod(state / "pairings.json", 0o600)
    return config


def load_config(path: str | Path) -> NodeConfig:
    raw = json.loads(Path(path).read_text())
    return NodeConfig(
        endpoint=str(raw["endpoint"]),
        workspace_roots=tuple(str(item) for item in raw["workspaceRoots"]),
        emergency_stop_hotkey=raw.get("emergencyStopHotkey"),
        node_id=str(raw["nodeId"]),
        authority_id=str(raw["authorityId"]),
        device_name=str(raw["deviceName"]),
    )


def _load_node(config_path: str | Path, config: NodeConfig) -> NodeIdentity:
    return NodeIdentity.from_private_bytes(
        config.node_id, config.device_name, _read_secret(_state_dir(config_path) / "node.key")
    )


def _load_authority(config_path: str | Path, config: NodeConfig) -> CapabilityAuthorityIdentity:
    return CapabilityAuthorityIdentity.from_private_bytes(
        config.authority_id, _read_secret(_state_dir(config_path) / "authority.key")
    )


def _controller_key_path(config_path: str | Path, controller_id: str) -> Path:
    safe = "".join(ch for ch in controller_id if ch.isalnum() or ch in "-_")
    if safe != controller_id or not safe:
        raise ValueError("controller_id_not_filesystem_safe")
    return _state_dir(config_path) / f"controller-{safe}.key"


def _load_or_create_controller(config_path: str | Path, controller_id: str) -> ControllerIdentity:
    path = _controller_key_path(config_path, controller_id)
    if path.exists():
        return ControllerIdentity.from_private_bytes(controller_id, "capt-node-cli", _read_secret(path))
    controller = ControllerIdentity.generate(controller_id, "capt-node-cli")
    _write_secret(path, controller.private_key_bytes())
    return controller


def _serialize_pairing(record: PairingRecord) -> dict[str, object]:
    return {
        "nodeId": record.node_id,
        "controllerId": record.controller_id,
        "nodePublicKey": base64.b64encode(record.node_public_key).decode("ascii"),
        "controllerPublicKey": base64.b64encode(record.controller_public_key).decode("ascii"),
        "shortCode": record.short_code,
        "state": record.state.value,
        "reason": record.reason,
        "executionAuthority": False,
    }


def _deserialize_pairing(raw: dict[str, object]) -> PairingRecord:
    return PairingRecord(
        node_id=str(raw["nodeId"]),
        controller_id=str(raw["controllerId"]),
        node_public_key=base64.b64decode(str(raw["nodePublicKey"]), validate=True),
        controller_public_key=base64.b64decode(str(raw["controllerPublicKey"]), validate=True),
        short_code=str(raw["shortCode"]),
        state=PairingState(str(raw["state"])),
        reason=None if raw.get("reason") is None else str(raw["reason"]),
        execution_authority=False,
    )


def _load_pairings(config_path: str | Path) -> list[PairingRecord]:
    return _load_pairings_from(_state_dir(config_path) / "pairings.json")


def _load_pairings_from(path: Path) -> list[PairingRecord]:
    raw = json.loads(path.read_text()) if path.exists() else []
    return [_deserialize_pairing(item) for item in raw]


def _save_pairings(config_path: str | Path, records: list[PairingRecord]) -> None:
    path = _state_dir(config_path) / "pairings.json"
    path.write_text(json.dumps([_serialize_pairing(item) for item in records], sort_keys=True, indent=2) + "\n")
    os.chmod(path, 0o600)


def pair_controller(
    config_path: str | Path, controller_id: str, *, approve_code: str | None = None
) -> dict[str, object]:
    config = load_config(config_path)
    node = _load_node(config_path, config)
    controller = _load_or_create_controller(config_path, controller_id)
    pending = PairingRecord.pending(node, controller)
    records = [item for item in _load_pairings(config_path) if item.controller_id != controller_id]
    record = pending if approve_code is None else pending.activate(approve_code)
    records.append(record)
    _save_pairings(config_path, records)
    return {
        "controllerId": controller_id,
        "verificationCode": record.short_code,
        "state": record.state.value,
        "executionAuthority": False,
    }


def authorize_mcp_capability(
    config_path: str | Path,
    controller_id: str,
    output_path: str | Path,
    *,
    expires_minutes: int = 60,
) -> dict[str, object]:
    if expires_minutes < 1 or expires_minutes > 24 * 60:
        raise ValueError("mcp_capability_expiry_minutes_out_of_range")
    config = load_config(config_path)
    pairing = next(
        (item for item in _load_pairings(config_path) if item.controller_id == controller_id),
        None,
    )
    if pairing is None or pairing.state is not PairingState.ACTIVE:
        raise PermissionError("mcp_controller_pairing_not_active")
    controller_path = _controller_key_path(config_path, controller_id)
    if not controller_path.exists():
        raise PermissionError("mcp_controller_key_missing")
    authority = _load_authority(config_path, config)
    now = datetime.now(timezone.utc)
    capability = sign_capability(
        OperationCapability(
            capability_id="mcp-cap-" + uuid.uuid4().hex[:20],
            bot_id="mcp-controller",
            mission_id="mcp-session",
            task_id="mcp-session",
            controller_id=controller_id,
            node_id=config.node_id,
            permitted_operations=frozenset({"shell.exec"}),
            filesystem_roots=config.workspace_roots,
            issued_at=now,
            expires_at=now + timedelta(minutes=expires_minutes),
        ),
        authority,
    )
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"schemaVersion": "1.0.0", "capability": capability_to_wire(capability)}, sort_keys=True, indent=2) + "\n")
    os.chmod(target, 0o600)
    return {
        "capabilityId": capability.capability_id,
        "controllerId": controller_id,
        "nodeId": config.node_id,
        "filesystemRoots": list(config.workspace_roots),
        "expiresAt": capability.expires_at.isoformat(),
    }


def list_controllers(config_path: str | Path) -> list[dict[str, object]]:
    return [
        {
            "controllerId": item.controller_id,
            "state": item.state.value,
            "executionAuthority": False,
        }
        for item in _load_pairings(config_path)
    ]


def _socket_path(config: NodeConfig) -> Path:
    return Path(validate_endpoint(config.endpoint)[len("unix://"):])


def _workspace_root(config: NodeConfig, cwd: str) -> str:
    resolved = Path(cwd).resolve()
    matches = [Path(root).resolve() for root in config.workspace_roots if resolved.is_relative_to(Path(root).resolve())]
    if not matches:
        raise PermissionError("node_cli_cwd_outside_workspace_roots")
    return str(max(matches, key=lambda item: len(str(item))))


def execute_cli(
    config_path: str | Path,
    controller_id: str,
    *,
    operation_id: str,
    cwd: str,
    argv: list[str],
    timeout_ms: int = 30_000,
) -> dict[str, object]:
    if not argv:
        raise ValueError("node_cli_exec_argv_required")
    if isinstance(timeout_ms, bool) or timeout_ms < 1 or timeout_ms > 3_600_000:
        raise ValueError("node_cli_timeout_ms_out_of_range")
    config = load_config(config_path)
    controller = _load_or_create_controller(config_path, controller_id)
    authority = _load_authority(config_path, config)
    now = datetime.now(timezone.utc)
    capability = sign_capability(
        OperationCapability(
            capability_id="cli-" + operation_id,
            bot_id="human-operator-cli",
            mission_id="cli-dogfood",
            task_id="cli-" + operation_id,
            controller_id=controller.controller_id,
            node_id=config.node_id,
            permitted_operations=frozenset({"shell.exec"}),
            filesystem_roots=(_workspace_root(config, cwd),),
            issued_at=now,
            expires_at=now + timedelta(minutes=5),
        ),
        authority,
    )
    request = NodeOperationRequest(
        operation_id=operation_id,
        capability=capability,
        operation="shell.exec",
        arguments={"argv": argv, "cwd": cwd, "timeout_ms": timeout_ms},
        issued_at=now,
    )
    return NodeClient(_socket_path(config), controller).execute(request)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="capt-node")
    subs = parser.add_subparsers(dest="command", required=True)
    init = subs.add_parser("init")
    init.add_argument("--config", required=True)
    init.add_argument("--workspace", action="append", required=True)
    serve = subs.add_parser("serve")
    serve.add_argument("--config", required=True)
    status = subs.add_parser("status")
    status.add_argument("--config", required=True)
    status.add_argument("--controller-id")
    status.add_argument("--operation-id")
    pair = subs.add_parser("pair")
    pair.add_argument("--config", required=True)
    pair.add_argument("--controller-id", required=True)
    pair.add_argument("--approve-code")
    controllers = subs.add_parser("controllers")
    controllers.add_argument("--config", required=True)
    mcp_auth = subs.add_parser("mcp-authorize")
    mcp_auth.add_argument("--config", required=True)
    mcp_auth.add_argument("--controller-id", required=True)
    mcp_auth.add_argument("--capability-file", required=True)
    mcp_auth.add_argument("--expires-minutes", type=int, default=60)
    execute = subs.add_parser("exec")
    execute.add_argument("--config", required=True)
    execute.add_argument("--controller-id", required=True)
    execute.add_argument("--operation-id", required=True)
    execute.add_argument("--cwd", required=True)
    execute.add_argument("--timeout-ms", type=int, default=30_000)
    execute.add_argument("argv", nargs=argparse.REMAINDER)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "init":
        result: object = init_config(args.config, workspace_roots=args.workspace).to_dict()
    elif args.command == "pair":
        result = pair_controller(args.config, args.controller_id, approve_code=args.approve_code)
    elif args.command == "controllers":
        result = list_controllers(args.config)
    elif args.command == "status":
        config = load_config(args.config)
        if args.operation_id:
            if not args.controller_id:
                raise ValueError("node_status_controller_id_required")
            controller = _load_or_create_controller(args.config, args.controller_id)
            result = NodeClient(_socket_path(config), controller).status(args.operation_id)
        else:
            result = {
                "nodeId": config.node_id,
                "endpoint": config.endpoint,
                "socketPresent": _socket_path(config).exists(),
                "controllers": list_controllers(args.config),
            }
    elif args.command == "mcp-authorize":
        result = authorize_mcp_capability(
            args.config,
            args.controller_id,
            args.capability_file,
            expires_minutes=args.expires_minutes,
        )
    elif args.command == "exec":
        result = execute_cli(
            args.config,
            args.controller_id,
            operation_id=args.operation_id,
            cwd=args.cwd,
            argv=args.argv,
            timeout_ms=args.timeout_ms,
        )
    elif args.command == "serve":
        config = load_config(args.config)
        policy = ServiceIdentityPolicy.from_config(json.loads(Path(args.config).read_text()))
        if policy is None:
            # Legacy same-uid mode: everything lives next to the config.
            trust_dir = state_dir = _state_dir(args.config)
            service_report: dict[str, object] = {"mode": "legacy_same_uid"}
        else:
            trust_dir, state_dir = policy.trust_dir, policy.state_dir
            try:
                service_report = preflight(
                    policy,
                    config_path=Path(args.config).resolve(),
                    workspace_roots=config.workspace_roots,
                    code_root=Path(__file__).resolve().parents[2],
                    legacy_state_dir=_state_dir(args.config),
                )
            except ServicePreflightError as exc:
                print(json.dumps({"state": "refused", "code": exc.code, "detail": exc.detail}, sort_keys=True), flush=True)
                return 3
            service_report["mode"] = "service_identity"
        node = NodeIdentity.from_private_bytes(
            config.node_id, config.device_name, _read_secret(state_dir / "node.key")
        )
        authority_public = base64.b64decode(
            (trust_dir / "authority.pub").read_text().strip(), validate=True
        )
        journal = NodeOperationJournal(state_dir / "journal.sqlite")
        server = NodeServer(
            _socket_path(config),
            node,
            journal,
            pairings=[item for item in _load_pairings_from(trust_dir / "pairings.json") if item.state is PairingState.ACTIVE],
            authority_issuers={config.authority_id: authority_public},
            now=lambda: datetime.now(timezone.utc),
            service_policy=policy,
            service_roots=config.workspace_roots,
            denial_log=DenialLog(state_dir / "denials.jsonl") if policy is not None else None,
        )
        server.start()
        print(json.dumps({"nodeId": config.node_id, "endpoint": config.endpoint, "state": "serving",
                          "service": service_report}, sort_keys=True), flush=True)
        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            server.close()
            journal.close()
        return 0
    else:
        raise RuntimeError("node_cli_command_dispatch_unreachable")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
