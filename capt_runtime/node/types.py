"""Typed CAPT Node operation and capability contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Mapping


class NodeOperationState(str, Enum):
    PREPARED = "prepared"
    RESERVED = "reserved"
    DISPATCHED = "dispatched"
    ACCEPTED = "accepted"
    EXECUTING = "executing"
    EFFECT_OBSERVED = "effect_observed"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    CLOSED = "closed"
    REJECTED = "rejected"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REVOKED = "revoked"
    TIMED_OUT = "timed_out"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    INDETERMINATE = "indeterminate"
    BLOCKED_HUMAN = "blocked_human"
    QUARANTINED = "quarantined"


@dataclass(frozen=True)
class OperationCapability:
    capability_id: str
    bot_id: str
    mission_id: str
    task_id: str
    controller_id: str
    node_id: str
    permitted_operations: frozenset[str]
    filesystem_roots: tuple[str, ...]
    issued_at: datetime
    expires_at: datetime
    authority_issuer_id: str | None = None
    authority_signature: str | None = None

    def require_authorized(
        self,
        operation: str,
        *,
        node_id: str,
        controller_id: str,
        at: datetime,
    ) -> None:
        if operation not in self.permitted_operations:
            raise PermissionError("operation_not_permitted")
        if node_id != self.node_id:
            raise PermissionError("node_identity_mismatch")
        if controller_id != self.controller_id:
            raise PermissionError("controller_identity_mismatch")
        if at < self.issued_at:
            raise PermissionError("capability_not_yet_valid")
        if at >= self.expires_at:
            raise PermissionError("capability_expired")


@dataclass(frozen=True)
class NodeOperationRequest:
    operation_id: str
    capability: OperationCapability
    operation: str
    arguments: Mapping[str, Any]
    issued_at: datetime


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, frozenset):
        return sorted(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def canonical_request_digest(request: NodeOperationRequest) -> str:
    payload = _jsonable(asdict(request))
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class NodeOperationResult:
    operation_id: str
    state: NodeOperationState
    evidence: tuple[Mapping[str, Any], ...] = ()
    exit_code: int | None = None
    detail: str | None = None
    specific_reason: str | None = None

    def __post_init__(self) -> None:
        reason = self.specific_reason or self.detail
        if reason in {"error", "unknown", "generic"}:
            raise ValueError("node result reason must be specific")
