"""Trusted model-operator agent tool mode configuration."""
from __future__ import annotations

import os

AGENT_TOOL_PROFILE = "capt-workspace-mcp:agent:v1"
AGENT_TOOL_OPERATIONS = (
    "file.read", "file.search", "file.write", "file.patch", "terminal.exec",
)


def configured_agent_tool_mode(driver_run_id: str) -> dict[str, object]:
    enabled = os.environ.get("CAPT_MODEL_OPERATOR_TOOLBRIDGE", "").strip().lower() in {
        "1", "true", "yes", "on",
    }
    return {
        "enabled": enabled,
        "profile": AGENT_TOOL_PROFILE if enabled else "",
        "operations": list(AGENT_TOOL_OPERATIONS) if enabled else [],
        "grantId": ("g-agent-tools-" + driver_run_id) if enabled else "",
        "leaseId": ("l-agent-tools-" + driver_run_id) if enabled else "",
    }
