from __future__ import annotations

import stat

from capt_runtime.mcp import MCPServerRegistry


def test_registry_seeds_state_bound_capt_and_shared_android_server(tmp_path):
    state = tmp_path / "edition-state"
    registry = MCPServerRegistry(state)

    servers = registry.server_configs()

    assert set(servers) == {"capt", "another"}
    assert servers["capt"]["type"] == "stdio"
    assert servers["capt"]["command"] == "capt-workspace-mcp"
    assert servers["capt"]["environment"]["CAPT_STATE_DIR"] == str(state)
    assert servers["another"] == {
        "type": "http",
        "url": "http://localhost:7070/mcp",
    }
    mode = stat.S_IMODE((state / "mcp_servers.json").stat().st_mode)
    assert mode == 0o600


import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from capt_runtime.mcp import MCPHTTPClient


def test_http_client_initializes_lists_and_calls_tools():
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length))
            seen.append((request, self.headers.get("Mcp-Session-Id")))
            method = request.get("method")
            if method == "notifications/initialized":
                self.send_response(202)
                self.end_headers()
                return
            if method == "initialize":
                result = {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "android-share", "version": "1"},
                }
            elif method == "tools/list":
                result = {
                    "tools": [
                        {
                            "name": "screen_state",
                            "description": "Read current Android screen state",
                            "inputSchema": {"type": "object", "properties": {}},
                            "annotations": {"readOnlyHint": True},
                        }
                    ]
                }
            elif method == "tools/call":
                assert request["params"] == {"name": "screen_state", "arguments": {}}
                result = {
                    "content": [{"type": "text", "text": "ready"}],
                    "isError": False,
                }
            else:
                raise AssertionError(method)
            body = json.dumps(
                {"jsonrpc": "2.0", "id": request["id"], "result": result}
            ).encode()
            self.send_response(200)
            if method == "initialize":
                self.send_header("Mcp-Session-Id", "session-android")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = MCPHTTPClient(f"http://127.0.0.1:{server.server_port}/mcp", timeout=2)
        initialized = client.initialize()
        assert initialized["serverInfo"]["name"] == "android-share"
        tools = client.list_tools()
        assert [tool["name"] for tool in tools] == ["screen_state"]
        result = client.call_tool("screen_state", {})
        assert result["content"][0]["text"] == "ready"
        assert seen[1][1] == "session-android"
        assert seen[2][1] == "session-android"
        assert seen[3][1] == "session-android"
    finally:
        server.shutdown()
        server.server_close()


import sys

from capt_runtime.mcp import MCPStdioClient


def test_stdio_client_propagates_state_root_and_lists_and_calls_tools(tmp_path):
    server = tmp_path / "server.py"
    server.write_text(
        """import json, os, sys\nfor line in sys.stdin:\n    req=json.loads(line)\n    method=req.get("method")\n    if method=="notifications/initialized":\n        continue\n    if method=="initialize":\n        result={"protocolVersion":"2025-06-18","capabilities":{"tools":{}},"serverInfo":{"name":"capt-test","version":"1"},"state":os.environ.get("CAPT_STATE_DIR")}\n    elif method=="tools/list":\n        result={"tools":[{"name":"workspace_status","description":"status","inputSchema":{"type":"object","properties":{}},"annotations":{"readOnlyHint":True}}]}\n    elif method=="tools/call":\n        result={"content":[{"type":"text","text":req["params"]["name"]}],"isError":False}\n    else:\n        result={}\n    print(json.dumps({"jsonrpc":"2.0","id":req["id"],"result":result}), flush=True)\n"""
    )
    client = MCPStdioClient(
        [sys.executable, str(server)],
        environment={"CAPT_STATE_DIR": str(tmp_path / "edition")},
        timeout=2,
    )
    try:
        initialized = client.initialize()
        assert initialized["state"] == str(tmp_path / "edition")
        assert [tool["name"] for tool in client.list_tools()] == ["workspace_status"]
        result = client.call_tool("workspace_status", {})
        assert result["content"][0]["text"] == "workspace_status"
    finally:
        client.close()


from capt_runtime.mcp import MCPToolAdapter, mcp_tool_descriptor


class RecordingMCPClient:
    def __init__(self):
        self.calls = []

    def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return {"content": [{"type": "text", "text": "ok"}], "isError": False}


def test_mcp_descriptor_namespaces_tools_and_conservatively_classifies_effects():
    read_tool = {
        "name": "screen_state",
        "description": "Read screen",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": {"readOnlyHint": True},
    }
    write_tool = {
        "name": "tap",
        "description": "Tap screen",
        "inputSchema": {"type": "object", "properties": {"x": {"type": "integer"}}},
    }
    read = mcp_tool_descriptor("another", read_tool)
    write = mcp_tool_descriptor("another", write_tool)
    assert read["toolId"] == "mcp.another.screen_state"
    assert read["operationEffects"] == [
        {"operation": "mcp.call", "effectClass": "pure_read_only"}
    ]
    assert read["requiredCapabilities"] == ["mcp.call"]
    assert write["toolId"] == "mcp.another.tap"
    assert write["operationEffects"] == [
        {"operation": "mcp.call", "effectClass": "durable_remote"}
    ]
    assert write["requiredCapabilities"] == ["mcp.call"]


def test_mcp_adapter_uses_typed_arguments_and_observes_consequential_dispatch():
    client = RecordingMCPClient()
    tool = {
        "name": "tap",
        "description": "Tap screen",
        "inputSchema": {"type": "object"},
    }
    descriptor = mcp_tool_descriptor("another", tool)
    adapter = MCPToolAdapter("another", tool, client, descriptor)
    observed = []
    request = {
        "toolId": descriptor["toolId"],
        "operation": "mcp.call",
        "arguments": [
            {"kind": "integer", "name": "x", "value": 10},
            {"kind": "integer", "name": "y", "value": 20},
        ],
        "idempotencyKey": "idem-mcp-tap",
        "consequential": True,
        "backendId": "local",
    }
    result = adapter.execute_observed(request, observed.append)
    assert client.calls == [("tap", {"x": 10, "y": 20})]
    assert observed == ["mcp-dispatch:another:tap:idem-mcp-tap"]
    assert result["status"] == "succeeded"
    assert result["sideEffectIdentity"] == observed[0]


def test_capt_loopback_tool_is_not_importable():
    tool = {
        "name": "capt_runtime_snapshot",
        "description": "loop",
        "inputSchema": {"type": "object"},
        "annotations": {"readOnlyHint": True},
    }
    import pytest

    with pytest.raises(ValueError, match="loopback"):
        mcp_tool_descriptor("capt", tool)


from capt_runtime.mcp import MCPManager


def test_manager_discovers_http_server_and_exposes_truthful_snapshot(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            req = json.loads(self.rfile.read(length))
            method = req.get("method")
            if method == "notifications/initialized":
                self.send_response(202)
                self.end_headers()
                return
            if method == "initialize":
                result = {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "android", "version": "1"},
                }
            elif method == "tools/list":
                result = {
                    "tools": [
                        {
                            "name": "screen_state",
                            "description": "read",
                            "inputSchema": {"type": "object"},
                            "annotations": {"readOnlyHint": True},
                        }
                    ]
                }
            else:
                result = {"content": [], "isError": False}
            body = json.dumps(
                {"jsonrpc": "2.0", "id": req["id"], "result": result}
            ).encode()
            self.send_response(200)
            if method == "initialize":
                self.send_header("Mcp-Session-Id", "s1")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    state = tmp_path / "state"
    state.mkdir()
    (state / "mcp_servers.json").write_text(
        json.dumps(
            {
                "schemaVersion": "1.0.0",
                "mcpServers": {
                    "another": {
                        "type": "http",
                        "url": f"http://127.0.0.1:{server.server_port}/mcp",
                    }
                },
            }
        )
    )
    try:
        manager = MCPManager(state, timeout=2)
        snapshot = manager.refresh_all()
        assert snapshot["servers"][0]["serverId"] == "another"
        assert snapshot["servers"][0]["status"] == "available"
        assert snapshot["servers"][0]["toolCount"] == 1
        bindings = manager.tool_bindings()
        assert [binding[0]["toolId"] for binding in bindings] == [
            "mcp.another.screen_state"
        ]
        manager.close()
    finally:
        server.shutdown()
        server.server_close()


from capt_runtime.composition import create_runtime


def test_runtime_composition_registers_discovered_mcp_tools_when_enabled(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            req = json.loads(self.rfile.read(length))
            method = req.get("method")
            if method == "notifications/initialized":
                self.send_response(202)
                self.end_headers()
                return
            if method == "initialize":
                result = {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "android", "version": "1"},
                }
            elif method == "tools/list":
                result = {
                    "tools": [
                        {
                            "name": "screen_state",
                            "inputSchema": {"type": "object"},
                            "annotations": {"readOnlyHint": True},
                        }
                    ]
                }
            else:
                result = {"content": [], "isError": False}
            body = json.dumps(
                {"jsonrpc": "2.0", "id": req["id"], "result": result}
            ).encode()
            self.send_response(200)
            if method == "initialize":
                self.send_header("Mcp-Session-Id", "s1")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    state = tmp_path / "state"
    state.mkdir()
    (state / "mcp_servers.json").write_text(
        json.dumps(
            {
                "schemaVersion": "1.0.0",
                "mcpServers": {
                    "another": {
                        "type": "http",
                        "url": f"http://127.0.0.1:{server.server_port}/mcp",
                    }
                },
            }
        )
    )
    try:
        runtime = create_runtime(
            str(state / "runtime.db"), enable_mcp=True, mcp_timeout=2
        )
        try:
            ids = {item["toolId"] for item in runtime.tool_registry.list_descriptors()}
            assert "mcp.another.screen_state" in ids
            assert runtime.mcp_manager.snapshot()["servers"][0]["status"] == "available"
        finally:
            runtime.close()
    finally:
        server.shutdown()
        server.server_close()


from desktop.capt_runtime_service import RuntimeQueryService


def test_runtime_query_projects_mcp_servers_and_capability(tmp_path):
    runtime = create_runtime(str(tmp_path / "runtime.db"))

    class Manager:
        def snapshot(self):
            return {
                "schemaVersion": "1.0.0",
                "stateDirectory": str(tmp_path),
                "servers": [
                    {"serverId": "another", "status": "unavailable", "toolCount": 0}
                ],
            }

    try:
        query = RuntimeQueryService(runtime.store, mcp_manager=Manager())
        caps = query.handle({"op": "capabilities"})["result"]
        assert "mcp_servers" in caps["queryOperations"]
        assert caps["runtimeComponents"]["mcpClient"] is True
        result = query.handle({"op": "mcp_servers"})["result"]
        assert result["servers"][0]["serverId"] == "another"
    finally:
        runtime.close()
