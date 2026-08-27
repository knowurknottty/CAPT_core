"""CAPT-owned binding for the canonical Workspace MCP agent profile.

MCP protocol/tool translation lives in capt-workspace-mcp. Core only freezes
run authority and emits an isolated Hermes configuration that points at it.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

MCP_SERVER_NAME = "capt_broker"


@dataclass(frozen=True)
class ToolBridgeBinding:
    grant_id: str
    lease_id: str
    filesystem_scope: str
    runtime_sock: str
    token_file: str


def _write_private(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    os.chmod(path, 0o600)


def write_agent_mcp_config(home: Path, binding: ToolBridgeBinding) -> Path:
    config = {
        "server": {"name": "capt-agent-toolbroker", "transport": "stdio"},
        "writes": {"audit_required": False},
        "audit": {"enabled": False, "fail_closed": True},
        "agent": {
            "runtime_socket": binding.runtime_sock,
            "token_file": binding.token_file,
            "grant_id": binding.grant_id,
            "lease_id": binding.lease_id,
            "filesystem_scope": str(Path(binding.filesystem_scope).resolve()),
        },
    }
    path = home / "capt-agent-mcp.yaml"
    _write_private(path, json.dumps(config, sort_keys=True, indent=2) + "\n")
    return path


def build_isolated_hermes_home(
    home: Path, *, mcp_executable: str, binding: ToolBridgeBinding,
    provider: str, model: str, provider_api_key: str,
) -> Path:
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(home, 0o700)
    command = str(Path(mcp_executable).resolve())
    if not Path(command).is_file():
        raise FileNotFoundError(f"CAPT Workspace MCP executable unavailable: {command}")
    agent_config = write_agent_mcp_config(home, binding)
    args = ["--profile", "agent", "--config", str(agent_config)]
    config = (
        f"capt_toolbridge:\n  provider: {provider}\n  model: {model}\n"
        f"mcp_servers:\n  {MCP_SERVER_NAME}:\n"
        f"    command: {json.dumps(command)}\n"
        f"    args: {json.dumps(args)}\n"
        "    timeout: 600\n    connect_timeout: 30\n"
        "    supports_parallel_tool_calls: false\n"
    )
    _write_private(home / "config.yaml", config)
    env_name = {"openrouter": "OPENROUTER_API_KEY"}.get(provider.lower())
    if provider_api_key and env_name is None:
        raise ValueError(f"unsupported isolated Hermes provider credential: {provider}")
    _write_private(home / ".env", f"{env_name}={provider_api_key}\n" if provider_api_key else "")
    return home
