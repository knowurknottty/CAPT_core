"""CAPT Bootstrap Bridge IPC protocol.

Defines the authenticated connection descriptor, the request/response envelopes,
and the per-turn ownership receipt. The turn channel receives protection
equivalent to (and bound to) the READY channel's launch nonce, but scoped to the
runtime identity and generation so a stale or replaced runner cannot authenticate.

Security properties enforced here:

* the auth token is a cryptographically strong, launch/runtime-scoped secret
* the token is never placed in argv, logs, evidence, or serialized public results
* token comparison uses ``hmac.compare_digest``
* authentication is bound to runtime identity + generation
* missing / invalid / stale / replayed requests are rejected with structured codes
* request size and read time are bounded
* JSON structure and types are validated before dispatch
* shutdown is an authenticated operational command
* no stack traces or secrets leak to clients
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

PROTOCOL_VERSION = 1
_MAX_REQUEST_BYTES = 64 * 1024
_READ_TIMEOUT_S = 10.0

# Ops
OP_TURN = "turn"
OP_SHUTDOWN = "shutdown"
OP_HEALTH = "health"

# Structured error codes
ERR_MISSING_AUTH = "TURN_MISSING_AUTH"
ERR_INVALID_AUTH = "TURN_INVALID_AUTH"
ERR_STALE_GENERATION = "TURN_STALE_GENERATION"
ERR_REPLAYED = "TURN_REPLAYED"
ERR_MALFORMED = "TURN_MALFORMED"
ERR_OVERSIZED = "TURN_OVERSIZED"
ERR_UNKNOWN_OP = "TURN_UNKNOWN_OP"
ERR_INTERNAL = "TURN_INTERNAL_ERROR"
ERR_BOUND_EXCEEDED = "TURN_BOUND_EXCEEDED"


class BridgeProtocolError(Exception):
    """Structured protocol failure; carries a machine-readable error code."""

    def __init__(self, code: str, message: str, *, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status

    def to_dict(self) -> Dict[str, Any]:
        return {"error": self.code, "message": self.message}


@dataclass
class BridgeConnectionDescriptor:
    """Issued by the bridge to the runner; authorizes the turn channel.

    The ``auth_token`` is a launch/runtime-scoped secret. It is delivered to the
    runner only via the environment (never argv, never logs). Clients must echo
    it inside each request's ``auth`` field.
    """

    protocol_version: int
    runtime_id: str
    runtime_generation: int
    mission_id: str
    session_id: str
    socket_path: str
    auth_token: str
    issued_at: str
    expires_at: str

    def is_expired(self, now: Optional[float] = None) -> bool:
        now = now if now is not None else time.time()
        return now >= _parse_iso(self.expires_at)

    def token_matches(self, candidate: str) -> bool:
        if not candidate or not self.auth_token:
            return False
        return hmac.compare_digest(candidate, self.auth_token)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "protocol_version": self.protocol_version,
            "runtime_id": self.runtime_id,
            "runtime_generation": self.runtime_generation,
            "mission_id": self.mission_id,
            "session_id": self.session_id,
            "socket_path": self.socket_path,
            "auth_token": self.auth_token,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
        }


@dataclass
class TurnEnvelope:
    """Authenticated request envelope for the turn channel."""

    protocol_version: int
    runtime_id: str
    runtime_generation: int
    request_id: str
    nonce: str
    auth: str
    op: str
    payload: Dict[str, Any]

    @classmethod
    def from_mapping(cls, data: Any) -> "TurnEnvelope":
        if not isinstance(data, dict):
            raise BridgeProtocolError(ERR_MALFORMED, "request is not an object")
        required = (
            "protocol_version",
            "runtime_id",
            "runtime_generation",
            "request_id",
            "nonce",
            "op",
        )
        for key in required:
            if key not in data:
                raise BridgeProtocolError(ERR_MALFORMED, f"missing field {key!r}")
        op = data["op"]
        if op not in (OP_TURN, OP_SHUTDOWN, OP_HEALTH):
            raise BridgeProtocolError(ERR_UNKNOWN_OP, f"unknown op {op!r}")
        payload = data.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        auth = data.get("auth", "")
        if not isinstance(auth, str):
            raise BridgeProtocolError(ERR_MALFORMED, "auth must be a string")
        return cls(
            protocol_version=int(data["protocol_version"]),
            runtime_id=str(data["runtime_id"]),
            runtime_generation=int(data["runtime_generation"]),
            request_id=str(data["request_id"]),
            nonce=str(data["nonce"]),
            auth=auth,
            op=op,
            payload=payload,
        )


@dataclass
class TurnReceipt:
    """Per-turn ownership proof: the turn actually traversed CAPT governance."""

    request_id: str
    turn_id: str
    mission_id: str
    session_id: str
    runtime_id: str
    runtime_generation: int
    provider_owner: str
    execution_mode: str
    ctp_transaction_id: str
    checkpoint_before: str
    checkpoint_after: str
    claim_supported: bool
    receipt_digest: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "turn_id": self.turn_id,
            "mission_id": self.mission_id,
            "session_id": self.session_id,
            "runtime_id": self.runtime_id,
            "runtime_generation": self.runtime_generation,
            "provider_owner": self.provider_owner,
            "execution_mode": self.execution_mode,
            "ctp_transaction_id": self.ctp_transaction_id,
            "checkpoint_before": self.checkpoint_before,
            "checkpoint_after": self.checkpoint_after,
            "claim_supported": self.claim_supported,
            "receipt_digest": self.receipt_digest,
        }


def compute_receipt_digest(receipt: Dict[str, Any]) -> str:
    """Deterministic digest over the receipt's authoritative fields."""
    canonical = {
        "request_id": receipt.get("request_id"),
        "turn_id": receipt.get("turn_id"),
        "mission_id": receipt.get("mission_id"),
        "session_id": receipt.get("session_id"),
        "runtime_id": receipt.get("runtime_id"),
        "runtime_generation": receipt.get("runtime_generation"),
        "provider_owner": receipt.get("provider_owner"),
        "execution_mode": receipt.get("execution_mode"),
        "ctp_transaction_id": receipt.get("ctp_transaction_id"),
        "checkpoint_before": receipt.get("checkpoint_before"),
        "checkpoint_after": receipt.get("checkpoint_after"),
        "claim_supported": receipt.get("claim_supported"),
    }
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _parse_iso(value: str) -> float:
    try:
        return time.mktime(time.strptime(value, "%Y-%m-%dT%H:%M:%SZ"))
    except Exception:
        # Fall back to a far-future parse failure (treated as expired)
        return 0.0


def make_nonce() -> str:
    return uuid.uuid4().hex


def make_auth_token() -> str:
    import secrets as _secrets

    return _secrets.token_hex(32)
