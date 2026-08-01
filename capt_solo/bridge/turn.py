"""Governed turn execution — route an Intent into the live CAPT runner.

The bridge does not generate text. It sends the Intent to the already-running,
already-governed CAPT Agent Runner over its private, authenticated turn socket
and returns what CAPT produced. When CAPT cannot execute the turn, the bridge
reports that fact; it never substitutes its own answer and never falls back to a
Hermes provider.

The request carries an authenticated ``TurnEnvelope`` (runtime-scoped auth token,
request id, nonce) so the runner can reject unauthenticated, invalid, stale, or
replayed requests. The response carries a ``TurnReceipt`` proving the turn
actually traversed CAPT governance.
"""

from __future__ import annotations

import json
import logging
import socket
import uuid
from typing import Any, Optional

from capt_solo.bridge.contracts import BridgeResult
from capt_solo.bridge.protocol import (
    OP_SHUTDOWN,
    OP_TURN,
    TurnEnvelope,
)

logger = logging.getLogger(__name__)

TURN_TIMEOUT_S = 600.0
_MAX_INTENT_CHARS = 200_000
_MAX_OUTPUT_CHARS = 200_000


def execute_governed_turn(
    result: Optional[BridgeResult],
    intent: str,
    *,
    handle: Any = None,
) -> str:
    """Execute one governed turn through the live CAPT runner."""
    if result is None or not result.provider_allowed:
        return _envelope(
            "BLOCKED",
            {
                "reason": "governed turn requested without a validated bridge result",
                "provider_owner": result.provider_owner if result else "NONE_WHEN_BLOCKED",
            },
        )

    turn_socket = getattr(handle, "turn_socket_path", "") if handle is not None else ""
    if not turn_socket:
        return _envelope(
            "BLOCKED",
            {"reason": "no live CAPT turn channel; runner is not serving governed turns"},
        )

    runtime_id = getattr(handle, "runtime_id", "")
    runtime_generation = getattr(handle, "runtime_generation", 0)
    turn_auth = getattr(handle, "turn_auth", "")
    if not turn_auth:
        return _envelope(
            "BLOCKED",
            {"reason": "turn channel is not authenticated; refusing to send unauthenticated request"},
        )

    envelope = TurnEnvelope(
        protocol_version=1,
        runtime_id=runtime_id,
        runtime_generation=runtime_generation,
        request_id=uuid.uuid4().hex,
        nonce=uuid.uuid4().hex,
        auth=turn_auth,
        op=OP_TURN,
        payload={"intent": intent[:_MAX_INTENT_CHARS]},
    )
    payload = json.dumps(envelope.__dict__, sort_keys=True, default=str).encode("utf-8")
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(TURN_TIMEOUT_S)
            s.connect(turn_socket)
            s.sendall(payload)
            s.shutdown(socket.SHUT_WR)
            chunks = []
            total = 0
            while total < _MAX_OUTPUT_CHARS:
                data = s.recv(8192)
                if not data:
                    break
                chunks.append(data)
                total += len(data)
        raw = b"".join(chunks).decode("utf-8", errors="replace")
    except socket.timeout:
        return _envelope("BLOCKED", {"reason": f"governed turn timed out after {TURN_TIMEOUT_S:g}s"})
    except Exception as exc:
        return _envelope(
            "BLOCKED", {"reason": f"governed turn channel failed: {type(exc).__name__}: {exc}"}
        )

    try:
        resp = json.loads(raw)
    except Exception:
        return _envelope("BLOCKED", {"reason": "CAPT turn response was not valid JSON"})

    if not resp.get("ok"):
        return _envelope(
            "BLOCKED",
            {
                "reason": resp.get("error") or "CAPT turn did not succeed",
                "provider_owner": resp.get("provider_owner", result.provider_owner),
                "execution_mode": resp.get("execution_mode", result.execution_mode),
            },
        )

    text = str(resp.get("output") or "")
    if len(text) > _MAX_OUTPUT_CHARS:
        text = text[:_MAX_OUTPUT_CHARS] + "\n[...truncated by bridge output bound...]"

    receipt = resp.get("receipt") or {}
    return (
        "CAPT GOVERNED TURN\n"
        f"mission={result.mission_id} session={result.session_id} "
        f"checkpoint={resp.get('checkpoint_id') or result.checkpoint_id}\n"
        f"provider_owner={result.provider_owner} execution_mode={result.execution_mode}\n"
        f"contextpack={result.contextpack_digest} gate={result.memory_use_gate}\n"
        f"ctp={resp.get('tx_id') or result.ctp_transaction_id} "
        f"khsb={result.khsb_correlation_id}\n"
        f"intent_id={resp.get('intent_id', '')} "
        f"claim_supported={resp.get('claim_supported')}\n"
        f"turn_receipt_runtime={receipt.get('runtime_id', '')} "
        f"gen={receipt.get('runtime_generation', '')} "
        f"receipt_digest={receipt.get('receipt_digest', '')}\n\n"
        f"{text}"
    )


def shutdown_runner_turns(handle: Any) -> bool:
    """Ask the runner to stop serving and checkpoint coherently (authenticated)."""
    turn_socket = getattr(handle, "turn_socket_path", "") if handle is not None else ""
    if not turn_socket:
        return False
    turn_auth = getattr(handle, "turn_auth", "")
    runtime_id = getattr(handle, "runtime_id", "")
    runtime_generation = getattr(handle, "runtime_generation", 0)
    if not turn_auth:
        return False
    envelope = TurnEnvelope(
        protocol_version=1,
        runtime_id=runtime_id,
        runtime_generation=runtime_generation,
        request_id=uuid.uuid4().hex,
        nonce=uuid.uuid4().hex,
        auth=turn_auth,
        op=OP_SHUTDOWN,
        payload={},
    )
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(30.0)
            s.connect(turn_socket)
            s.sendall(json.dumps(envelope.__dict__, sort_keys=True, default=str).encode("utf-8"))
            s.recv(4096)
        return True
    except Exception:
        return False


def _envelope(status: str, payload: dict) -> str:
    return "CAPT BRIDGE TURN " + status + "\n" + json.dumps(
        payload, indent=2, sort_keys=True, default=str
    )
