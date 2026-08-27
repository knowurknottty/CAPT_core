"""CAPT-governed MCP tool bridge for isolated Hermes executions."""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .tool_broker import tool_request_fingerprint

MCP_SERVER_NAME = "capt_broker"
_TOOL_NAMES = (
    "capt_terminal",
    "capt_read_file",
    "capt_search_files",
    "capt_write_file",
    "capt_patch_file",
)


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }


def mcp_tool_definitions() -> list[dict[str, Any]]:
    """Return the only model-visible tools in a CAPT bridge session."""
    path = {"type": "string", "minLength": 1}
    integer = {"type": "integer", "minimum": 1}
    return [
        {
            "name": "capt_terminal",
            "description": "Run one argv-form command through CAPT ToolBroker inside the bound worktree.",
            "inputSchema": _schema(
                {
                    "argv": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
                    "cwd": {"type": "string", "default": "."},
                    "timeout_ms": {**integer, "maximum": 3_600_000},
                },
                ["argv"],
            ),
        },
        {
            "name": "capt_read_file",
            "description": "Read a UTF-8 file through CAPT ToolBroker within the bound worktree.",
            "inputSchema": _schema({"path": path, "offset": {"type": "integer", "minimum": 0}}, ["path"]),
        },
        {
            "name": "capt_search_files",
            "description": "Search text through CAPT ToolBroker within the bound worktree.",
            "inputSchema": _schema(
                {"search_root": {"type": "string", "default": "."}, "query": path,
                 "max_results": {"type": "integer", "minimum": 1, "maximum": 500},
                 "case_sensitive": {"type": "boolean"}},
                ["query"],
            ),
        },
        {
            "name": "capt_write_file",
            "description": "Write a file through CAPT ToolBroker within the bound worktree.",
            "inputSchema": _schema({"path": path, "content": {"type": "string"}}, ["path", "content"]),
        },
        {
            "name": "capt_patch_file",
            "description": "Replace an exact occurrence count through CAPT ToolBroker within the bound worktree.",
            "inputSchema": _schema(
                {"path": path, "old": {"type": "string", "minLength": 1}, "new": {"type": "string"},
                 "expected_replacements": {"type": "integer", "minimum": 0}},
                ["path", "old", "new", "expected_replacements"],
            ),
        },
    ]


def _safe_identifier(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.:-]", "-", value)[:80].strip("-") or "call"
    return cleaned


def _arg(kind: str, name: str, value: Any) -> dict[str, Any]:
    return {"kind": kind, "name": name, "value": value}


@dataclass(frozen=True)
class ToolBridgeBinding:
    grant_id: str
    lease_id: str
    filesystem_scope: str
    runtime_sock: str
    token_file: str

    def _path(self, value: str) -> str:
        root = Path(self.filesystem_scope).resolve()
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = root / candidate
        resolved = candidate.resolve(strict=False)
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ValueError("tool path escapes CAPT filesystem scope") from exc
        return str(resolved)

    def build_tool_request(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        request_id: str,
        requested_at: str,
    ) -> dict[str, Any]:
        tool_id, operation, consequential, items = self._translate(tool_name, arguments)
        idem = "tb-" + hashlib.sha256(request_id.encode("utf-8")).hexdigest()[:24]
        request = {
            "schemaVersion": "1.0.0",
            "toolRequestId": "tr-" + _safe_identifier(request_id),
            "toolId": tool_id,
            "operation": operation,
            "arguments": items,
            "consequential": consequential,
            "leaseId": self.lease_id,
            "reservationId": None,
            "idempotencyKey": idem,
            "operationFingerprint": "sha256:" + "0" * 64,
            "replayPolicy": "never",
            "requestedAt": requested_at,
            "grantId": self.grant_id,
            "backendId": "local",
            "targetIdentity": self.filesystem_scope,
            "filesystemScope": self.filesystem_scope,
        }
        request["operationFingerprint"] = tool_request_fingerprint(request)
        return request

    def _translate(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> tuple[str, str, bool, list[dict[str, Any]]]:
        if tool_name == "capt_terminal":
            argv = arguments.get("argv")
            if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
                raise ValueError("capt_terminal argv must be a non-empty string array")
            cwd = self._path(str(arguments.get("cwd", ".")))
            items = [_arg("string", "argv", json.dumps(argv)), _arg("path", "cwd", cwd)]
            if "timeout_ms" in arguments:
                items.append(_arg("integer", "timeout_ms", int(arguments["timeout_ms"])))
            return "terminal.local", "terminal.exec", True, items
        if tool_name == "capt_read_file":
            items = [_arg("path", "path", self._path(str(arguments["path"])))]
            if "offset" in arguments:
                items.append(_arg("integer", "offset", int(arguments["offset"])))
            return "file.operations", "file.read", False, items
        if tool_name == "capt_search_files":
            items = [
                _arg("path", "search_root", self._path(str(arguments.get("search_root", ".")))),
                _arg("string", "query", str(arguments["query"])),
            ]
            if "max_results" in arguments:
                items.append(_arg("integer", "max_results", int(arguments["max_results"])))
            if "case_sensitive" in arguments:
                items.append(_arg("boolean", "case_sensitive", bool(arguments["case_sensitive"])))
            return "file.operations", "file.search", False, items
        if tool_name == "capt_write_file":
            items = [
                _arg("path", "path", self._path(str(arguments["path"]))),
                _arg("string", "content", str(arguments["content"])),
            ]
            return "file.operations", "file.write", True, items
        if tool_name == "capt_patch_file":
            items = [
                _arg("path", "path", self._path(str(arguments["path"]))),
                _arg("string", "old", str(arguments["old"])),
                _arg("string", "new", str(arguments["new"])),
                _arg("integer", "expected_replacements", int(arguments["expected_replacements"])),
            ]
            return "file.operations", "file.patch", True, items
        raise ValueError("unknown CAPT MCP tool: %s" % tool_name)


def _yaml_quote(value: str) -> str:
    return json.dumps(value)


def build_isolated_hermes_home(
    home: Path,
    *,
    bridge_argv: list[str],
    provider: str,
    model: str,
    provider_api_key: str,
) -> Path:
    """Create a per-run Hermes home containing only CAPT's MCP bridge config."""
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(home, 0o700)
    if not bridge_argv:
        raise ValueError("bridge_argv must not be empty")
    args_yaml = ", ".join(_yaml_quote(arg) for arg in bridge_argv[1:])
    config = (
        "capt_toolbridge:\n"
        f"  provider: {provider}\n"
        f"  model: {model}\n"
        "mcp_servers:\n"
        f"  {MCP_SERVER_NAME}:\n"
        f"    command: {_yaml_quote(bridge_argv[0])}\n"
        f"    args: [{args_yaml}]\n"
        "    timeout: 600\n"
        "    connect_timeout: 30\n"
        "    supports_parallel_tool_calls: false\n"
    )
    config_path = home / "config.yaml"
    config_path.write_text(config, encoding="utf-8")
    os.chmod(config_path, 0o600)
    env_name = {"openrouter": "OPENROUTER_API_KEY"}.get(provider.lower())
    if provider_api_key and env_name is None:
        raise ValueError("unsupported isolated Hermes provider credential: %s" % provider)
    env_path = home / ".env"
    env_path.write_text(
        (f"{env_name}={provider_api_key}\n" if provider_api_key else ""),
        encoding="utf-8",
    )
    os.chmod(env_path, 0o600)
    return home


def _rpc_result(message_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def _tool_result_text(receipt: dict[str, Any]) -> tuple[str, bool]:
    result = receipt.get("result", receipt)
    status = str(result.get("status", receipt.get("status", "failed")))
    output = result.get("output", [])
    rendered = []
    for item in output if isinstance(output, list) else []:
        if isinstance(item, dict):
            rendered.append(f"{item.get('name', 'value')}: {item.get('value', '')}")
    text = "\n".join(rendered) or json.dumps(result, sort_keys=True, default=str)
    return text, status not in {"accepted", "succeeded", "idempotent"}


def handle_mcp_message(
    message: dict[str, Any],
    binding: ToolBridgeBinding,
    execute_request,
) -> dict[str, Any] | None:
    """Handle the minimal MCP methods needed by an isolated Hermes session."""
    method = message.get("method")
    mid = message.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return _rpc_result(mid, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "capt-toolbridge", "version": "0.1.0"},
        })
    if method == "ping":
        return _rpc_result(mid, {})
    if method == "tools/list":
        return _rpc_result(mid, {"tools": mcp_tool_definitions()})
    if method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str) or not isinstance(arguments, dict):
            raise ValueError("malformed MCP tools/call")
        from datetime import datetime, timezone
        requested_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        request = binding.build_tool_request(
            name,
            arguments,
            request_id=str(mid if mid is not None else "notification"),
            requested_at=requested_at,
        )
        receipt = execute_request(request)
        text, is_error = _tool_result_text(receipt)
        return _rpc_result(mid, {
            "content": [{"type": "text", "text": text}],
            "isError": is_error,
        })
    if mid is None:
        return None
    return {
        "jsonrpc": "2.0",
        "id": mid,
        "error": {"code": -32601, "message": "Method not found"},
    }


def execute_via_runtime(
    binding: ToolBridgeBinding,
    request: dict[str, Any],
    *,
    client_factory=None,
) -> dict[str, Any]:
    """Execute one translated MCP call through CAPT's authenticated run_tool command."""
    if client_factory is None:
        from desktop.desktop_runtime_client import RuntimeClient
        client_factory = RuntimeClient
    client = client_factory(binding.runtime_sock, binding.token_file)
    try:
        client.connect()
        receipt = client.command("run_tool", request, request["idempotencyKey"])
    finally:
        client.disconnect()
    if receipt.get("status") not in {"accepted", "idempotent"}:
        raise RuntimeError(
            "CAPT ToolBroker command rejected: %s" % json.dumps(receipt, sort_keys=True, default=str)[:2000]
        )
    return receipt


def serve_stdio(
    binding: ToolBridgeBinding,
    execute_request,
    *,
    input_stream=None,
    output_stream=None,
) -> None:
    """Serve newline-delimited MCP JSON-RPC on stdio."""
    import sys
    source = input_stream or sys.stdin
    sink = output_stream or sys.stdout
    for raw in source:
        if not raw.strip():
            continue
        message_id = None
        try:
            message = json.loads(raw)
            message_id = message.get("id") if isinstance(message, dict) else None
            if not isinstance(message, dict):
                raise ValueError("MCP request must be an object")
            response = handle_mcp_message(message, binding, execute_request)
        except Exception as exc:
            if message_id is None:
                continue
            response = {
                "jsonrpc": "2.0", "id": message_id,
                "error": {"code": -32603, "message": type(exc).__name__ + ": " + str(exc)[:500]},
            }
        if response is not None:
            sink.write(json.dumps(response, separators=(",", ":")) + "\n")
            sink.flush()


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="python -m capt_runtime.hermes_toolbridge")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="serve the CAPT ToolBroker MCP bridge on stdio")
    serve.add_argument("--sock", required=True)
    serve.add_argument("--token-file", required=True)
    serve.add_argument("--grant-id", required=True)
    serve.add_argument("--lease-id", required=True)
    serve.add_argument("--filesystem-scope", required=True)
    args = parser.parse_args(argv)
    if args.command != "serve":
        parser.error("unsupported command")
    binding = ToolBridgeBinding(
        grant_id=args.grant_id,
        lease_id=args.lease_id,
        filesystem_scope=str(Path(args.filesystem_scope).resolve()),
        runtime_sock=args.sock,
        token_file=args.token_file,
    )
    serve_stdio(binding, lambda request: execute_via_runtime(binding, request))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
