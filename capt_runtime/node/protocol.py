"""Canonical, bounded CAPT Node RPC framing and wire conversion."""

from __future__ import annotations

import json
import struct
from datetime import datetime
from typing import Any

from .types import NodeOperationRequest, OperationCapability

MAX_FRAME_BYTES = 1024 * 1024


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def encode_frame(value: dict[str, Any]) -> bytes:
    payload = canonical_json(value)
    if len(payload) > MAX_FRAME_BYTES:
        raise ValueError("frame_too_large")
    return struct.pack("!I", len(payload)) + payload


def decode_frame(frame: bytes) -> dict[str, Any]:
    if len(frame) < 4:
        raise ValueError("frame_too_short")
    size = struct.unpack("!I", frame[:4])[0]
    if size > MAX_FRAME_BYTES:
        raise ValueError("frame_too_large")
    if len(frame) != size + 4:
        raise ValueError("frame_length_mismatch")
    try:
        value = json.loads(frame[4:].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("frame_json_invalid") from exc
    if not isinstance(value, dict):
        raise ValueError("frame_root_not_object")
    return value


def capability_to_wire(cap: OperationCapability) -> dict[str, Any]:
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
        "authoritySignature": cap.authority_signature,
    }


def capability_from_wire(cap: dict[str, Any]) -> OperationCapability:
    return OperationCapability(
        capability_id=str(cap["capabilityId"]),
        bot_id=str(cap["botId"]),
        mission_id=str(cap["missionId"]),
        task_id=str(cap["taskId"]),
        controller_id=str(cap["controllerId"]),
        node_id=str(cap["nodeId"]),
        permitted_operations=frozenset(str(item) for item in cap["permittedOperations"]),
        filesystem_roots=tuple(str(item) for item in cap.get("filesystemRoots", [])),
        issued_at=datetime.fromisoformat(str(cap["issuedAt"])),
        expires_at=datetime.fromisoformat(str(cap["expiresAt"])),
        authority_issuer_id=(str(cap["authorityIssuerId"]) if cap.get("authorityIssuerId") is not None else None),
        authority_signature=(str(cap["authoritySignature"]) if cap.get("authoritySignature") is not None else None),
    )


def request_to_wire(request: NodeOperationRequest) -> dict[str, Any]:
    return {
        "operationId": request.operation_id,
        "operation": request.operation,
        "arguments": dict(request.arguments),
        "issuedAt": request.issued_at.isoformat(),
        "capability": capability_to_wire(request.capability),
    }

def request_from_wire(value: dict[str, Any]) -> NodeOperationRequest:
    cap = value.get("capability")
    if not isinstance(cap, dict):
        raise ValueError("capability_missing")
    capability = capability_from_wire(cap)
    arguments = value.get("arguments")
    if not isinstance(arguments, dict):
        raise ValueError("arguments_not_object")
    return NodeOperationRequest(
        operation_id=str(value["operationId"]),
        capability=capability,
        operation=str(value["operation"]),
        arguments=arguments,
        issued_at=datetime.fromisoformat(str(value["issuedAt"])),
    )
