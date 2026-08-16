"""Bounded framed JSON transport helpers for local CAPT IPC.

The transport is intentionally tiny and deterministic: callers receive exactly
one JSON object per frame, partial headers/bodies are handled correctly, and a
peer-controlled length prefix can never trigger an unbounded allocation/read.
"""
from __future__ import annotations

import json
import socket
from typing import Any, Dict, Optional

MAX_FRAME_BYTES = 4 * 1024 * 1024


class FrameProtocolError(ValueError):
    pass


def _recv_exact(sock: socket.socket, size: int) -> Optional[bytes]:
    if size < 0:
        raise FrameProtocolError("IPC_FRAME_SIZE_NEGATIVE")
    buf = bytearray()
    while len(buf) < size:
        chunk = sock.recv(size - len(buf))
        if not chunk:
            if not buf:
                return None
            raise FrameProtocolError("IPC_FRAME_TRUNCATED")
        buf.extend(chunk)
    return bytes(buf)


def recv_json(sock: socket.socket, *, max_bytes: int = MAX_FRAME_BYTES) -> Optional[Dict[str, Any]]:
    if max_bytes <= 0 or max_bytes > 0xFFFFFFFF:
        raise ValueError("IPC_MAX_FRAME_INVALID")
    header = _recv_exact(sock, 4)
    if header is None:
        return None
    length = int.from_bytes(header, "big")
    if length <= 0:
        raise FrameProtocolError("IPC_FRAME_EMPTY")
    if length > max_bytes:
        raise FrameProtocolError("IPC_FRAME_TOO_LARGE:%d>%d" % (length, max_bytes))
    raw = _recv_exact(sock, length)
    if raw is None:
        raise FrameProtocolError("IPC_FRAME_TRUNCATED")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FrameProtocolError("IPC_FRAME_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise FrameProtocolError("IPC_FRAME_OBJECT_REQUIRED")
    return value


def send_json(sock: socket.socket, payload: Dict[str, Any], *, max_bytes: int = MAX_FRAME_BYTES) -> None:
    if max_bytes <= 0 or max_bytes > 0xFFFFFFFF:
        raise ValueError("IPC_MAX_FRAME_INVALID")
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if not data:
        raise FrameProtocolError("IPC_FRAME_EMPTY")
    if len(data) > max_bytes:
        raise FrameProtocolError("IPC_FRAME_TOO_LARGE:%d>%d" % (len(data), max_bytes))
    sock.sendall(len(data).to_bytes(4, "big") + data)
