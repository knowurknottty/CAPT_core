from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from capt_runtime.node.cli import (
    NodeConfig,
    build_parser,
    init_config,
    validate_endpoint,
)


def test_default_config_is_local_only_with_unbound_emergency_hotkey(tmp_path: Path):
    path = tmp_path / "node.json"
    config = init_config(path, workspace_roots=[str(tmp_path / "workspace")])
    assert config.endpoint.startswith("unix://")
    assert config.emergency_stop_hotkey is None
    assert config.workspace_roots == (str(tmp_path / "workspace"),)
    raw = json.loads(path.read_text())
    assert raw["emergencyStopHotkey"] is None


def test_tcp_and_public_endpoints_are_rejected():
    for endpoint in ("tcp://127.0.0.1:9000", "tcp://0.0.0.0:9000", "https://node.example"):
        with pytest.raises(ValueError, match="node_endpoint_must_be_local_unix_socket"):
            validate_endpoint(endpoint)


def test_config_requires_explicit_workspace_roots(tmp_path: Path):
    with pytest.raises(ValueError, match="node_workspace_roots_required"):
        NodeConfig(endpoint=f"unix://{tmp_path / 'node.sock'}", workspace_roots=())


def test_cli_exposes_operator_commands_without_generic_remote_shell():
    parser = build_parser()
    commands = parser._subparsers._group_actions[0].choices
    assert {"init", "serve", "status", "pair", "controllers", "mcp-authorize", "exec"} <= set(commands)
    assert "shell" not in commands


def test_init_persists_private_material_mode_0600_and_public_verifier(tmp_path: Path):
    path = tmp_path / "node.json"
    init_config(path, workspace_roots=[str(tmp_path / "workspace")])
    state = tmp_path / ".capt-node-state"
    for name in ("node.key", "authority.key", "authority.pub", "pairings.json"):
        target = state / name
        assert target.exists()
        assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert (state / "authority.pub").read_text().strip()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_cli_exec_accepts_explicit_bounded_timeout():
    args = build_parser().parse_args(
        [
            "exec",
            "--config", "/tmp/node.json",
            "--controller-id", "controller-1",
            "--operation-id", "op-1",
            "--cwd", "/tmp/workspace",
            "--timeout-ms", "90000",
            "python3", "-m", "pytest",
        ]
    )
    assert args.timeout_ms == 90_000
    assert args.argv == ["python3", "-m", "pytest"]
