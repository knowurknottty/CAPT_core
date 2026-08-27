from __future__ import annotations

import json
import os
from pathlib import Path

from capt_runtime.hermes_toolbridge import (
    MCP_SERVER_NAME, ToolBridgeBinding, build_isolated_hermes_home,
)


def _fake_executable(path: Path, text: str = "#!/bin/sh\nexit 0\n") -> Path:
    path.write_text(text)
    path.chmod(0o700)
    return path


def test_isolated_home_points_to_canonical_workspace_mcp_agent_profile(tmp_path: Path) -> None:
    mcp = _fake_executable(tmp_path / "capt-workspace-mcp")
    scope = tmp_path / "repo"
    scope.mkdir()
    binding = ToolBridgeBinding(
        grant_id="g-1", lease_id="l-1", filesystem_scope=str(scope),
        runtime_sock="/tmp/capt.sock", token_file="/tmp/capt.token",
    )
    home = build_isolated_hermes_home(
        tmp_path / "home", mcp_executable=str(mcp), binding=binding,
        provider="openrouter", model="z-ai/glm-5.3-flash", provider_api_key="secret",
    )
    agent = json.loads((home / "capt-agent-mcp.yaml").read_text())
    assert agent["agent"] == {
        "filesystem_scope": str(scope.resolve()), "grant_id": "g-1",
        "lease_id": "l-1", "runtime_socket": "/tmp/capt.sock",
        "token_file": "/tmp/capt.token",
    }
    hermes = (home / "config.yaml").read_text()
    assert MCP_SERVER_NAME in hermes
    assert str(mcp.resolve()) in hermes
    assert "--profile" in hermes and "agent" in hermes
    assert "capt_runtime.hermes_toolbridge" not in hermes
    assert "secret" not in hermes
    assert (home / ".env").read_text() == "OPENROUTER_API_KEY=secret\n"
    assert oct(os.stat(home / "capt-agent-mcp.yaml").st_mode & 0o777) == "0o600"


def test_runtime_composition_propagates_workspace_mcp_binding(tmp_path: Path) -> None:
    from capt_runtime.composition import create_runtime
    hermes = _fake_executable(tmp_path / "hermes", "#!/bin/sh\nprintf 'ok\n'\n")
    mcp = _fake_executable(tmp_path / "capt-workspace-mcp")
    binding = ToolBridgeBinding("g-2", "l-2", str(tmp_path), "/tmp/sock", "/tmp/token")
    runtime = create_runtime(str(tmp_path / "runtime.db"))
    try:
        host = runtime.hermes_host(
            target_repo=str(tmp_path), staging_root=str(tmp_path / "staging"),
            executable=str(hermes), enforce_memory=False, dispatch_prompt="task",
            tool_bridge_binding=binding, provider_id="openrouter",
            provider_model="z-ai/glm-5.3-flash", provider_api_key="secret",
            workspace_mcp_executable=str(mcp),
        )
        assert host._driver._tool_bridge_binding is binding
        assert host._driver._workspace_mcp_executable == str(mcp)
    finally:
        runtime.close()
