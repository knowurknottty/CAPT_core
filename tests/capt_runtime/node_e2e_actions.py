"""Actions run as a *real* Unix user by test_node_service_identity_e2e.py.

Usage: python node_e2e_actions.py <action> '<json-args>'  → prints one JSON object.
Never prints key material: only codes, states, exit codes and captured process output.
"""
from __future__ import annotations

import json
import socket
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _operator(config: str, controller_id: str):
    from capt_runtime.node.cli import _load_authority, _load_or_create_controller, _socket_path, load_config
    cfg = load_config(config)
    return cfg, _load_or_create_controller(config, controller_id), _load_authority(config, cfg), _socket_path(cfg)


def _request(cfg, controller, authority, *, op_id: str, roots: list[str], argv: list[str], cwd: str):
    from capt_runtime.node.authority import sign_capability
    from capt_runtime.node.types import NodeOperationRequest, OperationCapability
    now = datetime.now(timezone.utc)
    cap = sign_capability(OperationCapability(
        capability_id="e2e-" + op_id, bot_id="e2e", mission_id="e2e", task_id=op_id,
        controller_id=controller.controller_id, node_id=cfg.node_id,
        permitted_operations=frozenset({"shell.exec"}), filesystem_roots=tuple(roots),
        issued_at=now, expires_at=now + timedelta(minutes=5)), authority)
    return NodeOperationRequest(operation_id=op_id, capability=cap, operation="shell.exec",
                                arguments={"argv": argv, "cwd": cwd, "timeout_ms": 20_000}, issued_at=now)


def main() -> None:
    action, args = sys.argv[1], json.loads(sys.argv[2] if len(sys.argv) > 2 else "{}")
    import os
    try:
        if action == "whoami":
            out = {"uid": os.getuid(), "euid": os.geteuid(), "groups": sorted(os.getgroups())}
        elif action == "exec":
            from capt_runtime.node.client import NodeClient
            cfg, ctl, auth, sock = _operator(args["config"], args["controller"])
            req = _request(cfg, ctl, auth, op_id=args["op"], roots=args.get("roots") or list(cfg.workspace_roots),
                           argv=args["argv"], cwd=args["cwd"])
            res = NodeClient(sock, ctl).execute(req)
            ev = (res.get("evidence") or [{}])[0]
            out = {"state": res.get("state"), "exitCode": res.get("exitCode"), "replayed": res.get("replayed"),
                   "stdout": ev.get("stdout"), "stderr": ev.get("stderr")}
        elif action == "status":
            from capt_runtime.node.client import NodeClient
            cfg, ctl, auth, sock = _operator(args["config"], args["controller"])
            res = NodeClient(sock, ctl).status(args["op"])
            out = {"state": res.get("state")}
        elif action == "raw_connect":
            # Connect to the Node socket and send an unsigned frame: proves who can reach it.
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect(args["socket"])
            body = json.dumps({"kind": "status", "controllerId": "x", "payload": {"operationId": "x"},
                               "signature": "AA=="}).encode()
            s.sendall(len(body).to_bytes(4, "big") + body)
            size = int.from_bytes(s.recv(4), "big")
            out = {"connected": True, "response": json.loads(s.recv(size).decode())}
        elif action == "read":
            out = {"readable": True, "bytes": len(Path(args["path"]).read_bytes())}
        else:
            raise SystemExit("unknown action")
    except PermissionError as exc:
        out = {"error": "PermissionError", "code": str(exc).split(":")[0] if str(exc) else "EACCES"}
    except OSError as exc:
        out = {"error": type(exc).__name__, "errno": exc.errno}
    except Exception as exc:  # noqa: BLE001 - report the code, never a traceback with paths
        code, _, detail = str(exc).partition(" ")
        out = {"error": type(exc).__name__, "code": code, "detail": detail}
    print(json.dumps(out, default=str))


if __name__ == "__main__":
    main()
