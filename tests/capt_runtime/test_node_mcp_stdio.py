from __future__ import annotations

from capt_runtime.node.mcp_stdio import MCPStdioSession


class FakeSurface:
    def list_tools(self):
        return [{"name": "node_status", "description": "status"}]

    def call_tool(self, name, arguments):
        if name != "node_status":
            raise ValueError(f"mcp_tool_not_supported:{name}")
        return {"operationId": arguments["operationId"], "state": "closed"}


def _session():
    return MCPStdioSession(FakeSurface())


def test_initialize_advertises_tools_only():
    response = _session().handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert response["result"]["capabilities"] == {"tools": {}}
    assert response["result"]["serverInfo"]["name"] == "capt-node"


def test_tools_list_contains_only_surface_tools():
    response = _session().handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    assert response["result"]["tools"] == [
        {
            "name": "node_status",
            "description": "status",
            "inputSchema": {"type": "object", "additionalProperties": True},
        }
    ]


def test_tools_call_returns_structured_content():
    response = _session().handle(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "node_status", "arguments": {"operationId": "op-1"}},
        }
    )
    assert response["result"]["structuredContent"]["state"] == "closed"
    assert response["result"]["isError"] is False


def test_unknown_method_is_specific_jsonrpc_error():
    response = _session().handle(
        {"jsonrpc": "2.0", "id": 4, "method": "resources/list", "params": {}}
    )
    assert response["error"]["code"] == -32601
    assert response["error"]["message"] == "mcp_method_not_supported:resources/list"


def test_notification_returns_no_response():
    response = _session().handle(
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
    )
    assert response is None
