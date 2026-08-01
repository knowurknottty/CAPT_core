"""Governed turn execution — route an Intent into the live CAPT runner.

The bridge does not generate text. It sends the Intent to the already-running,
already-governed CAPT Agent Runner over its private turn socket and returns what
CAPT produced. When CAPT cannot execute the turn, the bridge reports that fact;
it never substitutes its own answer and never falls back to a Hermes provider.
"""

from __future__ import annotations

import json
import logging
import socket
from typing import Any, Optional

from capt_solo.bridge.contracts import BridgeResult

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

    payload = json.dumps({"op": "turn", "intent": intent[:_MAX_INTENT_CHARS]}) + "\n"
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(TURN_TIMEOUT_S)
            s.connect(turn_socket)
            s.sendall(payload.encode("utf-8"))
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

    return (
        "CAPT GOVERNED TURN\n"
        f"mission={result.mission_id} session={result.session_id} "
        f"checkpoint={resp.get('checkpoint_id') or result.checkpoint_id}\n"
        f"provider_owner={result.provider_owner} execution_mode={result.execution_mode}\n"
        f"contextpack={result.contextpack_digest} gate={result.memory_use_gate}\n"
        f"ctp={resp.get('tx_id') or result.ctp_transaction_id} "
        f"khsb={result.khsb_correlation_id}\n"
        f"intent_id={resp.get('intent_id', '')} "
        f"claim_supported={resp.get('claim_supported')}\n\n"
        f"{text}"
    )


def shutdown_runner_turns(handle: Any) -> bool:
    """Ask the runner to stop serving and checkpoint coherently."""
    turn_socket = getattr(handle, "turn_socket_path", "") if handle is not None else ""
    if not turn_socket:
        return False
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(30.0)
            s.connect(turn_socket)
            s.sendall((json.dumps({"op": "shutdown"}) + "\n").encode("utf-8"))
            s.recv(4096)
        return True
    except Exception:
        return False


def _envelope(status: str, payload: dict) -> str:
    return "CAPT BRIDGE TURN " + status + "\n" + json.dumps(
        payload, indent=2, sort_keys=True, default=str
    )
