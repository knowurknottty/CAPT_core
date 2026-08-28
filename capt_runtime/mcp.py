"""State-bound MCP server registry for CAPT runtime-owned MCP clients."""

from __future__ import annotations

import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any


class MCPServerRegistry:
    def __init__(self, state_dir: str | Path) -> None:
        self.state_dir = Path(state_dir).expanduser()
        self.path = self.state_dir / "mcp_servers.json"
        self._ensure_config()

    def _defaults(self) -> dict[str, dict[str, Any]]:
        return {
            "capt": {
                "type": "stdio",
                "command": "capt-workspace-mcp",
                "args": ["--profile", "chatgpt", "--server", "stdio"],
                "environment": {"CAPT_STATE_DIR": str(self.state_dir)},
            },
            "another": {
                "type": "http",
                "url": "http://localhost:7070/mcp",
            },
        }

    def _ensure_config(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            return
        payload = {"schemaVersion": "1.0.0", "mcpServers": self._defaults()}
        fd, temp_name = tempfile.mkstemp(
            prefix=".mcp-servers-", dir=str(self.state_dir)
        )
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8", closefd=True) as handle:
                fd = -1
                json.dump(payload, handle, sort_keys=True, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
            os.chmod(self.path, 0o600)
        finally:
            if fd >= 0:
                os.close(fd)
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

    def server_configs(self) -> dict[str, dict[str, Any]]:
        with self.path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        servers = payload.get("mcpServers")
        if not isinstance(servers, dict):
            raise TypeError("mcpServers must be an object")
        return deepcopy(servers)


from urllib import error as urllib_error
from urllib import request as urllib_request

MCP_PROTOCOL_VERSION = "2025-06-18"


class MCPError(RuntimeError):
    pass


class MCPUnavailable(MCPError):
    pass


def _decode_http_response(body: bytes, content_type: str) -> dict[str, Any] | None:
    if not body:
        return None
    text = body.decode("utf-8", errors="strict")
    if "text/event-stream" in content_type:
        payloads = []
        for line in text.splitlines():
            if line.startswith("data:"):
                payloads.append(line[5:].strip())
        if not payloads:
            raise MCPError("MCP SSE response contained no data event")
        text = payloads[-1]
    decoded = json.loads(text)
    if not isinstance(decoded, dict):
        raise MCPError("MCP response must be a JSON object")
    return decoded


class MCPHTTPClient:
    def __init__(self, url: str, *, timeout: float = 5.0) -> None:
        self.url = url
        self.timeout = timeout
        self.session_id: str | None = None
        self._next_id = 1
        self.initialized = False

    def _post(
        self, payload: dict[str, Any], *, expect_response: bool
    ) -> dict[str, Any] | None:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        req = urllib_request.Request(
            self.url,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib_request.urlopen(req, timeout=self.timeout) as response:
                session_id = response.headers.get("Mcp-Session-Id")
                if session_id:
                    self.session_id = session_id
                body = response.read()
                if not expect_response:
                    return None
                decoded = _decode_http_response(
                    body, response.headers.get("Content-Type", "")
                )
        except (urllib_error.URLError, TimeoutError, OSError) as exc:
            raise MCPUnavailable(
                f"HTTP MCP unavailable: {type(exc).__name__}: {exc}"
            ) from exc
        if decoded is None:
            raise MCPError("MCP request returned no response")
        if decoded.get("error") is not None:
            raise MCPError(f"MCP error: {decoded['error']}")
        result = decoded.get("result")
        if not isinstance(result, dict):
            raise MCPError("MCP response result must be an object")
        return result

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        result = self._post(
            {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
            expect_response=True,
        )
        assert result is not None
        return result

    def _notification(self, method: str, params: dict[str, Any]) -> None:
        self._post(
            {"jsonrpc": "2.0", "method": method, "params": params},
            expect_response=False,
        )

    def initialize(self) -> dict[str, Any]:
        result = self._request(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "capt-runtime", "version": "0.5.0"},
            },
        )
        self._notification("notifications/initialized", {})
        self.initialized = True
        return result

    def list_tools(self) -> list[dict[str, Any]]:
        if not self.initialized:
            self.initialize()
        result = self._request("tools/list", {})
        tools = result.get("tools", [])
        if not isinstance(tools, list) or not all(
            isinstance(tool, dict) for tool in tools
        ):
            raise MCPError("MCP tools/list returned invalid tools")
        return [deepcopy(tool) for tool in tools]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if not self.initialized:
            self.initialize()
        return self._request(
            "tools/call", {"name": name, "arguments": deepcopy(arguments)}
        )

    def close(self) -> None:
        return None


import selectors
import subprocess


class MCPStdioClient:
    def __init__(
        self,
        command: list[str],
        *,
        environment: dict[str, str] | None = None,
        timeout: float = 5.0,
    ) -> None:
        if not command or not all(isinstance(part, str) and part for part in command):
            raise ValueError("MCP stdio command must be a non-empty argv list")
        self.command = list(command)
        self.environment = dict(environment or {})
        self.timeout = timeout
        self._next_id = 1
        self.initialized = False
        self._process: subprocess.Popen[str] | None = None

    def _ensure_process(self) -> subprocess.Popen[str]:
        process = self._process
        if process is not None and process.poll() is None:
            return process
        env = os.environ.copy()
        env.update(self.environment)
        try:
            process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                env=env,
                shell=False,
            )
        except OSError as exc:
            raise MCPUnavailable(
                f"stdio MCP unavailable: {type(exc).__name__}: {exc}"
            ) from exc
        self._process = process
        return process

    def _send(self, payload: dict[str, Any]) -> None:
        process = self._ensure_process()
        if process.stdin is None:
            raise MCPUnavailable("stdio MCP stdin unavailable")
        try:
            process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
            process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise MCPUnavailable(
                f"stdio MCP write failed: {type(exc).__name__}: {exc}"
            ) from exc

    def _read_response(self, expected_id: int) -> dict[str, Any]:
        process = self._ensure_process()
        if process.stdout is None:
            raise MCPUnavailable("stdio MCP stdout unavailable")
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        try:
            events = selector.select(self.timeout)
        finally:
            selector.close()
        if not events:
            raise MCPUnavailable(f"stdio MCP response timed out after {self.timeout}s")
        line = process.stdout.readline()
        if not line:
            raise MCPUnavailable("stdio MCP exited before response")
        try:
            decoded = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MCPError("stdio MCP returned invalid JSON") from exc
        if not isinstance(decoded, dict) or decoded.get("id") != expected_id:
            raise MCPError("stdio MCP response id mismatch")
        if decoded.get("error") is not None:
            raise MCPError(f"MCP error: {decoded['error']}")
        result = decoded.get("result")
        if not isinstance(result, dict):
            raise MCPError("stdio MCP response result must be an object")
        return result

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        self._send(
            {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        )
        return self._read_response(request_id)

    def _notification(self, method: str, params: dict[str, Any]) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def initialize(self) -> dict[str, Any]:
        result = self._request(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "capt-runtime", "version": "0.5.0"},
            },
        )
        self._notification("notifications/initialized", {})
        self.initialized = True
        return result

    def list_tools(self) -> list[dict[str, Any]]:
        if not self.initialized:
            self.initialize()
        result = self._request("tools/list", {})
        tools = result.get("tools", [])
        if not isinstance(tools, list) or not all(
            isinstance(tool, dict) for tool in tools
        ):
            raise MCPError("MCP tools/list returned invalid tools")
        return [deepcopy(tool) for tool in tools]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if not self.initialized:
            self.initialize()
        return self._request(
            "tools/call", {"name": name, "arguments": deepcopy(arguments)}
        )

    def close(self) -> None:
        process = self._process
        self._process = None
        if process is None or process.poll() is not None:
            return
        try:
            process.terminate()
            process.wait(timeout=1)
        except (subprocess.TimeoutExpired, OSError):
            process.kill()
            try:
                process.wait(timeout=1)
            except (subprocess.TimeoutExpired, OSError):
                pass


import hashlib
import re


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _safe_component(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9_.:-]+", "_", value.lower()).strip("._:-")
    if not normalized:
        normalized = "tool"
    return normalized[:96]


def mcp_tool_descriptor(server_id: str, tool: dict[str, Any]) -> dict[str, Any]:
    name = tool.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("MCP tool requires a non-empty name")
    if server_id == "capt" and name.startswith("capt_"):
        raise ValueError(
            "CAPT MCP loopback tools are not importable into CAPT ToolBroker"
        )
    annotations = (
        tool.get("annotations") if isinstance(tool.get("annotations"), dict) else {}
    )
    read_only = annotations.get("readOnlyHint") is True
    effect = "pure_read_only" if read_only else "durable_remote"
    tool_id = f"mcp.{_safe_component(server_id)}.{_safe_component(name)}"
    if len(tool_id) > 128:
        suffix = hashlib.sha256(tool_id.encode("utf-8")).hexdigest()[:12]
        tool_id = tool_id[:115] + "." + suffix
    return {
        "schemaVersion": "1.0.0",
        "toolId": tool_id,
        "displayName": f"MCP {server_id}: {name}"[:128],
        "family": "mcp",
        "operations": ["mcp.call"],
        "requiredCapabilities": ["mcp.call"],
        "operationEffects": [{"operation": "mcp.call", "effectClass": effect}],
        "terminalBackends": ["local"],
        "platforms": ["macos", "linux"],
        "supportsTimeout": True,
        "supportsCancellation": False,
        "idempotencySupport": "broker_settled_replay",
        "artifactOutputs": ["mcp_result", "mcp_server", "mcp_tool", "schema_digest"],
    }


def _mcp_arguments(request: dict[str, Any]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for item in request.get("arguments", []):
        name = item.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("MCP argument requires a name")
        if name in parsed:
            raise ValueError(f"duplicate MCP argument: {name}")
        if name == "argumentsJson":
            raw = item.get("value")
            if not isinstance(raw, str):
                raise ValueError("argumentsJson must be a string")
            decoded = json.loads(raw)
            if not isinstance(decoded, dict):
                raise ValueError("argumentsJson must decode to an object")
            for key, value in decoded.items():
                if key in parsed:
                    raise ValueError(f"duplicate MCP argument: {key}")
                parsed[key] = value
            continue
        parsed[name] = item.get("value")
    return parsed


class MCPToolAdapter:
    supports_reconciliation = False

    def __init__(
        self,
        server_id: str,
        tool: dict[str, Any],
        client: Any,
        descriptor: dict[str, Any],
    ) -> None:
        self.server_id = server_id
        self.tool = deepcopy(tool)
        self.client = client
        self.descriptor = deepcopy(descriptor)
        self.adapter_id = "adapter-" + descriptor["toolId"]
        self.schema_digest = _canonical_digest(tool.get("inputSchema", {}))

    def readiness(self) -> dict[str, object]:
        return {
            "status": "available",
            "reason": f"MCP server {self.server_id} discovered tool {self.tool['name']}",
        }

    def preflight(self, request: dict[str, Any]) -> None:
        if request.get("toolId") != self.descriptor["toolId"]:
            raise ValueError("MCP adapter toolId mismatch")
        if request.get("operation") != "mcp.call":
            raise ValueError("MCP adapter requires operation=mcp.call")
        if request.get("backendId") != "local":
            raise ValueError("MCP adapter requires backendId=local")
        _mcp_arguments(request)

    def _result(
        self, request: dict[str, Any], *, side_effect_identity: str | None
    ) -> dict[str, Any]:
        arguments = _mcp_arguments(request)
        result = self.client.call_tool(self.tool["name"], arguments)
        encoded = json.dumps(result, sort_keys=True, separators=(",", ":"))
        if len(encoded) > 65536:
            raise MCPError("MCP tool result exceeds CAPT ToolArgument bound")
        is_error = result.get("isError") is True
        return {
            "status": "failed" if is_error else "succeeded",
            "exitCode": None,
            "output": [
                {"kind": "string", "name": "mcpResult", "value": encoded},
                {"kind": "string", "name": "mcpServer", "value": self.server_id},
                {"kind": "string", "name": "mcpTool", "value": self.tool["name"]},
                {"kind": "string", "name": "schemaDigest", "value": self.schema_digest},
            ],
            "sideEffectIdentity": side_effect_identity,
            "error": None,
        }

    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        self.preflight(request)
        return self._result(request, side_effect_identity=None)

    def execute_observed(
        self, request: dict[str, Any], observe_effect
    ) -> dict[str, Any]:
        self.preflight(request)
        effect = self.descriptor["operationEffects"][0]["effectClass"]
        if effect == "pure_read_only":
            return self._result(request, side_effect_identity=None)
        dispatch_identity = (
            f"mcp-dispatch:{self.server_id}:{self.tool['name']}:"
            f"{request.get('idempotencyKey', 'unknown')}"
        )
        observe_effect(dispatch_identity)
        return self._result(request, side_effect_identity=dispatch_identity)


import shutil


class MCPManager:
    def __init__(self, state_dir: str | Path, *, timeout: float = 3.0) -> None:
        self.state_dir = Path(state_dir).expanduser()
        self.registry = MCPServerRegistry(self.state_dir)
        self.timeout = timeout
        self._sessions: dict[str, dict[str, Any]] = {}
        self._bindings: list[tuple[dict[str, Any], MCPToolAdapter]] = []

    def _resolve_stdio_command(self, config: dict[str, Any]) -> list[str]:
        command = config.get("command")
        args = config.get("args", [])
        if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
            raise ValueError("MCP stdio args must be a string array")
        if isinstance(command, list):
            if not command or not all(
                isinstance(part, str) and part for part in command
            ):
                raise ValueError("MCP stdio command array is invalid")
            return list(command) + list(args)
        if not isinstance(command, str) or not command:
            raise ValueError("MCP stdio command must be a string or argv array")
        candidates: list[str] = []
        if command == "capt-workspace-mcp":
            explicit = os.environ.get("CAPT_WORKSPACE_MCP_EXECUTABLE")
            if explicit:
                candidates.append(str(Path(explicit).expanduser()))
        if os.path.isabs(command):
            candidates.append(command)
        else:
            found = shutil.which(command)
            if found:
                candidates.append(found)
        if command == "capt-workspace-mcp":
            home = Path.home()
            candidates.extend(
                [
                    str(
                        home
                        / "capt-workspace-mcp"
                        / ".venv"
                        / "bin"
                        / "capt-workspace-mcp"
                    ),
                    str(
                        home
                        / ".capt-workspace-mcp"
                        / "venv"
                        / "bin"
                        / "capt-workspace-mcp"
                    ),
                ]
            )
        for candidate in candidates:
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return [candidate] + list(args)
        raise MCPUnavailable(f"MCP stdio executable not found: {command}")

    def _client_for(self, config: dict[str, Any]):
        transport = config.get("type")
        if transport == "http":
            url = config.get("url")
            if not isinstance(url, str) or not url:
                raise ValueError("HTTP MCP server requires url")
            return MCPHTTPClient(url, timeout=self.timeout)
        if transport == "stdio":
            environment = config.get("environment", {})
            if not isinstance(environment, dict) or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in environment.items()
            ):
                raise ValueError("MCP stdio environment must be a string map")
            return MCPStdioClient(
                self._resolve_stdio_command(config),
                environment=environment,
                timeout=self.timeout,
            )
        raise ValueError(f"unsupported MCP transport: {transport!r}")

    def refresh_all(self) -> dict[str, Any]:
        self.close()
        self._sessions = {}
        self._bindings = []
        for server_id, config in sorted(self.registry.server_configs().items()):
            if not isinstance(server_id, str) or not server_id:
                continue
            if not isinstance(config, dict):
                self._sessions[server_id] = {
                    "serverId": server_id,
                    "status": "unavailable",
                    "reason": "server configuration is not an object",
                    "toolCount": 0,
                    "transport": "unknown",
                    "target": None,
                    "serverInfo": None,
                }
                continue
            client = None
            try:
                client = self._client_for(config)
                initialized = client.initialize()
                tools = client.list_tools()
                imported = 0
                for tool in tools:
                    try:
                        descriptor = mcp_tool_descriptor(server_id, tool)
                    except ValueError as exc:
                        if server_id == "capt" and "loopback" in str(exc):
                            continue
                        raise
                    adapter = MCPToolAdapter(server_id, tool, client, descriptor)
                    self._bindings.append((descriptor, adapter))
                    imported += 1
                self._sessions[server_id] = {
                    "serverId": server_id,
                    "status": "available",
                    "reason": "initialized and tools discovered",
                    "toolCount": imported,
                    "transport": config.get("type"),
                    "target": config.get("url")
                    if config.get("type") == "http"
                    else config.get("command"),
                    "serverInfo": deepcopy(initialized.get("serverInfo")),
                    "boundStateDirectory": (
                        config.get("environment", {}).get("CAPT_STATE_DIR")
                        if server_id == "capt"
                        else None
                    ),
                }
            except Exception as exc:  # noqa: BLE001
                if client is not None:
                    from contextlib import suppress

                    with suppress(Exception):
                        client.close()
                self._sessions[server_id] = {
                    "serverId": server_id,
                    "status": "unavailable",
                    "reason": f"{type(exc).__name__}: {exc}"[:2048],
                    "toolCount": 0,
                    "transport": config.get("type"),
                    "target": config.get("url")
                    if config.get("type") == "http"
                    else config.get("command"),
                    "serverInfo": None,
                    "boundStateDirectory": (
                        config.get("environment", {}).get("CAPT_STATE_DIR")
                        if server_id == "capt"
                        else None
                    ),
                }
            else:
                self._sessions[server_id]["_client"] = client
        return self.snapshot()

    def tool_bindings(self) -> list[tuple[dict[str, Any], MCPToolAdapter]]:
        return [
            (deepcopy(descriptor), adapter) for descriptor, adapter in self._bindings
        ]

    def snapshot(self) -> dict[str, Any]:
        servers = []
        for server_id in sorted(self._sessions):
            session = self._sessions[server_id]
            servers.append(
                {
                    key: deepcopy(value)
                    for key, value in session.items()
                    if key != "_client"
                }
            )
        return {
            "schemaVersion": "1.0.0",
            "stateDirectory": str(self.state_dir),
            "configPath": str(self.registry.path),
            "servers": servers,
        }

    def close(self) -> None:
        for session in getattr(self, "_sessions", {}).values():
            client = session.get("_client") if isinstance(session, dict) else None
            if client is not None:
                from contextlib import suppress

                with suppress(Exception):
                    client.close()
