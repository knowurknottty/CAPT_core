from __future__ import annotations

from capt_runtime.model_approval_binding import build_bound_model_operator_approval


def _bound(**overrides):
    base = dict(
        human_prompt="fix the bug", response_mode="SPOCK", enhancement_engine="OFF",
        mission_id="m-1", task_id="t-1", driver_run_id="dr-1", target_root="/tmp/repo",
        provider="openrouter", model="z-ai/glm-5.3-flash", requested_context_budget=32000,
        human_verification_required=True, executable="", staging_root="/tmp/staging",
    )
    base.update(overrides)
    return build_bound_model_operator_approval(**base)


def test_configured_agent_mode_is_deterministic_and_opt_in(monkeypatch):
    from capt_runtime.model_agent_tools import configured_agent_tool_mode
    monkeypatch.delenv("CAPT_MODEL_OPERATOR_TOOLBRIDGE", raising=False)
    assert configured_agent_tool_mode("dr-1")["enabled"] is False
    monkeypatch.setenv("CAPT_MODEL_OPERATOR_TOOLBRIDGE", "1")
    mode = configured_agent_tool_mode("dr-1")
    assert mode["enabled"] is True
    assert mode["profile"] == "capt-workspace-mcp:agent:v1"
    assert mode["grantId"] == "g-agent-tools-dr-1"
    assert mode["leaseId"] == "l-agent-tools-dr-1"
    assert set(mode["operations"]) == {
        "file.read", "file.search", "file.write", "file.patch", "terminal.exec"
    }


def test_agent_tool_profile_is_bound_into_approval_identity():
    normal = _bound()
    agent = _bound(
        agent_tool_profile="capt-workspace-mcp:agent:v1",
        agent_tool_operations=["file.read", "file.write", "terminal.exec"],
        agent_tool_grant_id="g-agent-tools-dr-1",
        agent_tool_lease_id="l-agent-tools-dr-1",
    )
    binding = agent["executionBinding"]
    assert binding["driverKind"] == "hermes-agent"
    assert binding["agentToolProfile"] == "capt-workspace-mcp:agent:v1"
    assert binding["agentToolOperations"] == ["file.read", "file.write", "terminal.exec"]
    assert binding["agentToolGrantId"] == "g-agent-tools-dr-1"
    assert binding["agentToolLeaseId"] == "l-agent-tools-dr-1"
    assert agent["promptAssemblyDigest"] != normal["promptAssemblyDigest"]
    assert "CAPT ToolBroker" in agent["dispatchPrompt"]
