"""stdio MCP adapter over the same capability-bound CAPT Node client."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from capt_runtime.mcp import MCP_PROTOCOL_VERSION

from .cli import (
    _load_or_create_controller,
    _socket_path,
    load_config,
)
from .client import NodeClient
from .mcp_server import NodeMCPServer
from .protocol import capability_from_wire


def load_capability_file(path: str | Path):
    raw = json.loads(Path(path).read_text())
    if not isinstance(raw, dict) or not isinstance(raw.get("capability"), dict):
        raise ValueError("mcp_capability_file_invalid")
    return capability_from_wire(raw["capability"])


def _tool_result(value: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": value,
        "isError": False,
    }

def _error_result(exc: Exception) -> dict[str, Any]:
    code = str(exc) or type(exc).__name__
    value = {"errorType": type(exc).__name__, "code": code}
    return {
        "content": [{"type": "text", "text": json.dumps(value, sort_keys=True)}],
        "structuredContent": value,
        "isError": True,
    }


class MCPStdioSession:
    def __init__(self, surface: NodeMCPServer) -> None:
        self.surface = surface

    @staticmethod
    def _tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = []
        for tool in tools:
            item = dict(tool)
            item.setdefault(
                "inputSchema",
                {"type": "object", "additionalProperties": True},
            )
            normalized.append(item)
        return normalized

    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        method = request.get("method")
        if method == "notifications/initialized":
            return None
        if method == "initialize":
            result = {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "capt-node", "version": "0.1.0"},
            }
        elif method == "tools/list":
            result = {"tools": self._tools(self.surface.list_tools())}
        elif method == "tools/call":
            params = request.get("params") or {}
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if not isinstance(name, str) or not isinstance(arguments, dict):
                result = _error_result(ValueError("mcp_tools_call_invalid"))
            else:
                try:
                    result = _tool_result(self.surface.call_tool(name, arguments))
                except Exception as exc:
                    result = _error_result(exc)
        else:
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {"code": -32601, "message": f"mcp_method_not_supported:{method}"},
            }
        return {"jsonrpc": "2.0", "id": request.get("id"), "result": result}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="capt-node-mcp")
    parser.add_argument("--config", required=True)
    parser.add_argument("--controller-id", required=True)
    parser.add_argument("--capability-file", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    controller = _load_or_create_controller(args.config, args.controller_id)
    capability = load_capability_file(args.capability_file)
    if capability.controller_id != controller.controller_id:
        raise PermissionError("mcp_capability_controller_mismatch")
    if capability.node_id != config.node_id:
        raise PermissionError("mcp_capability_node_mismatch")
    surface = NodeMCPServer(NodeClient(_socket_path(config), controller), capability)
    session = MCPStdioSession(surface)
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("mcp_request_root_not_object")
            response = session.handle(request)
        except Exception as exc:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": str(exc) or type(exc).__name__},
            }
        if response is not None:
            print(json.dumps(response, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
