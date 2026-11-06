"""Capability-bound MCP compatibility surface for CAPT Node."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .types import NodeOperationRequest, OperationCapability


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _scoped_cwd(capability: OperationCapability, raw: str) -> str:
    candidate = Path(raw).expanduser().resolve(strict=False)
    for root_text in capability.filesystem_roots:
        root = Path(root_text).expanduser().resolve(strict=False)
        try:
            candidate.relative_to(root)
            return str(candidate)
        except ValueError:
            continue
    raise PermissionError("mcp_cwd_outside_capability_scope")


class NodeMCPServer:
    """Expose Node calls using one pre-signed capability; never mint authority."""

    def __init__(self, client: Any, capability: OperationCapability, *, now: Callable[[], datetime] | None = None) -> None:
        self.client = client
        self.capability = capability
        self.now = now or _utcnow

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "node_exec",
                "description": "Execute explicit argv through a pre-authorized CAPT Node capability.",
                "inputSchema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["operationId", "cwd", "argv"],
                    "properties": {
                        "operationId": {"type": "string", "minLength": 1},
                        "cwd": {"type": "string", "minLength": 1},
                        "argv": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
                        "timeoutMs": {"type": "integer", "minimum": 1, "maximum": 3_600_000},
                    },
                },
            },
            {
                "name": "node_status",
                "description": "Read durable CAPT Node operation state by operation ID.",
                "inputSchema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["operationId"],
                    "properties": {"operationId": {"type": "string", "minLength": 1}},
                },
            },
            {
                "name": "node_evidence_read",
                "description": "Read one bounded chunk from a CAPT Node evidence reference.",
                "inputSchema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["operationId", "ref"],
                    "properties": {
                        "operationId": {"type": "string", "minLength": 1},
                        "ref": {"type": "string", "minLength": 1},
                        "offset": {"type": "integer", "minimum": 0},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 65536},
                    },
                },
            },
            {
                "name": "node_capability_info",
                "description": "Inspect non-secret bounds of the pre-authorized capability.",
                "inputSchema": {"type": "object", "additionalProperties": False, "properties": {}},
            },
        ]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "node_status":
            operation_id = arguments.get("operationId")
            if not isinstance(operation_id, str) or not operation_id:
                raise ValueError("mcp_operation_id_required")
            return self.client.status(operation_id)
        if name == "node_evidence_read":
            operation_id = arguments.get("operationId")
            ref = arguments.get("ref")
            offset = arguments.get("offset", 0)
            limit = arguments.get("limit", 64 * 1024)
            if not isinstance(operation_id, str) or not operation_id:
                raise ValueError("mcp_operation_id_required")
            if not isinstance(ref, str) or not ref:
                raise ValueError("mcp_evidence_ref_required")
            if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
                raise ValueError("mcp_evidence_offset_invalid")
            if isinstance(limit, bool) or not isinstance(limit, int):
                raise ValueError("mcp_evidence_limit_invalid")
            if limit < 1 or limit > 64 * 1024:
                raise ValueError("mcp_evidence_limit_out_of_range")
            return self.client.read_evidence(
                operation_id, ref, offset=offset, limit=limit
            )
        if name == "node_capability_info":
            cap = self.capability
            return {
                "capabilityId": cap.capability_id,
                "controllerId": cap.controller_id,
                "nodeId": cap.node_id,
                "permittedOperations": sorted(cap.permitted_operations),
                "filesystemRoots": list(cap.filesystem_roots),
                "issuedAt": cap.issued_at.isoformat(),
                "expiresAt": cap.expires_at.isoformat(),
                "authorityIssuerId": cap.authority_issuer_id,
            }
        if name != "node_exec":
            raise ValueError(f"mcp_tool_not_supported:{name}")

        operation_id = arguments.get("operationId")
        cwd = arguments.get("cwd")
        argv = arguments.get("argv")
        if not isinstance(operation_id, str) or not operation_id:
            raise ValueError("mcp_operation_id_required")
        if not isinstance(cwd, str) or not cwd:
            raise ValueError("mcp_cwd_required")
        if not isinstance(argv, list) or not argv or not all(
            isinstance(item, str) and item and "\x00" not in item for item in argv
        ):
            raise ValueError("mcp_argv_invalid")

        now = self.now()
        self.capability.require_authorized(
            "shell.exec",
            node_id=self.capability.node_id,
            controller_id=self.capability.controller_id,
            at=now,
        )
        timeout_ms = arguments.get("timeoutMs", 30_000)
        if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int):
            raise ValueError("mcp_timeout_ms_invalid")
        if timeout_ms < 1 or timeout_ms > 3_600_000:
            raise ValueError("mcp_timeout_ms_out_of_range")
        request = NodeOperationRequest(
            operation_id=operation_id,
            capability=self.capability,
            operation="shell.exec",
            arguments={
                "argv": list(argv),
                "cwd": _scoped_cwd(self.capability, cwd),
                "timeout_ms": timeout_ms,
            },
            issued_at=now,
        )
        return self.client.execute(request)

    def _capability_info(self) -> dict[str, Any]:
        cap = self.capability
        return {
            "capabilityId": cap.capability_id,
            "botId": cap.bot_id,
            "missionId": cap.mission_id,
            "taskId": cap.task_id,
            "controllerId": cap.controller_id,
            "nodeId": cap.node_id,
            "permittedOperations": sorted(cap.permitted_operations),
            "filesystemRoots": list(cap.filesystem_roots),
            "issuedAt": cap.issued_at.isoformat(),
            "expiresAt": cap.expires_at.isoformat(),
            "authorityIssuerId": cap.authority_issuer_id,
        }
