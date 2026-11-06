"""Local CAPT Node RPC client."""

from __future__ import annotations

import base64
import socket
from pathlib import Path
from typing import Any

from .identity import ControllerIdentity
from .protocol import canonical_json, decode_frame, encode_frame, request_to_wire
from .types import NodeOperationRequest


def operation_transport_timeout(request: NodeOperationRequest) -> float:
    raw = request.arguments.get("timeout_ms", 30_000)
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValueError("node_transport_timeout_ms_invalid")
    if raw < 1 or raw > 3_600_000:
        raise ValueError("node_transport_timeout_ms_out_of_range")
    return raw / 1000.0 + 5.0


class NodeClient:
    def __init__(self, socket_path: str | Path, controller: ControllerIdentity) -> None:
        self.socket_path = str(socket_path)
        self.controller = controller

    def _call(
        self, kind: str, payload: dict[str, Any], *, timeout_seconds: float = 5.0
    ) -> dict[str, Any]:
        unsigned = {
            "kind": kind,
            "controllerId": self.controller.controller_id,
            "payload": payload,
        }
        message = dict(unsigned)
        message["signature"] = base64.b64encode(
            self.controller.sign(canonical_json(unsigned))
        ).decode("ascii")
        frame = encode_frame(message)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout_seconds)
            sock.connect(self.socket_path)
            sock.sendall(frame)
            header = _recv_exact(sock, 4)
            size = int.from_bytes(header, "big")
            body = _recv_exact(sock, size)
        response = decode_frame(header + body)
        if response.get("ok") is not True:
            code = str(response.get("code") or "response_code_missing")
            if (
                code.startswith("controller_")
                or code.startswith("pairing_")
                or code.startswith("evidence_controller_")
                or code == "signature_invalid"
            ):
                raise PermissionError(code)
            raise RuntimeError(code)
        result = response.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("response_result_missing")
        return result

    def execute(self, request: NodeOperationRequest) -> dict[str, Any]:
        return self._call(
            "execute",
            request_to_wire(request),
            timeout_seconds=operation_transport_timeout(request),
        )

    def status(self, operation_id: str) -> dict[str, Any]:
        return self._call("status", {"operationId": operation_id})

    def read_evidence(
        self,
        operation_id: str,
        ref: str,
        *,
        offset: int = 0,
        limit: int = 64 * 1024,
    ) -> dict[str, Any]:
        return self._call(
            "evidence_read",
            {
                "operationId": operation_id,
                "ref": ref,
                "offset": offset,
                "limit": limit,
            },
        )


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = sock.recv(size - len(chunks))
        if not chunk:
            raise RuntimeError("rpc_connection_closed")
        chunks.extend(chunk)
    return bytes(chunks)
