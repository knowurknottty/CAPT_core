"""Closed Cloudflare Workflows identities and validation helpers."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

WORKFLOW_PROVIDER_STATUSES = frozenset({
    "queued", "running", "paused", "errored", "terminated",
    "complete", "waitingForPause", "waiting", "rollingBack",
})
_WORKFLOW_NAME_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
_EVENT_TYPE_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,100}$")
_INSTANCE_ID_RE = re.compile(r"^capt_[0-9a-f]{64}$")
MAX_WORKFLOW_START_PARAMS_BYTES = 32 * 1024
MAX_WORKFLOW_EVENT_BYTES = 16 * 1024


def workflow_instance_id(account_id: str, workflow_resource_id: str, operation_id: str) -> str:
    if not account_id or not workflow_resource_id or not operation_id:
        raise ValueError("cloudflare_workflow_instance_identity_required")
    raw = f"{account_id}\x00{workflow_resource_id}\x00{operation_id}".encode("utf-8")
    return "capt_" + hashlib.sha256(raw).hexdigest()


def require_workflow_instance_id(value: str) -> str:
    if not isinstance(value, str) or not _INSTANCE_ID_RE.fullmatch(value):
        raise ValueError("cloudflare_workflow_instance_id_invalid")
    return value


def require_workflow_name(value: str) -> str:
    if not isinstance(value, str) or not _WORKFLOW_NAME_RE.fullmatch(value):
        raise ValueError("cloudflare_workflow_name_invalid")
    return value


def require_event_type(value: str) -> str:
    if not isinstance(value, str) or not _EVENT_TYPE_RE.fullmatch(value):
        raise ValueError("cloudflare_workflow_event_type_invalid")
    return value


def canonical_json(value: Any, *, max_bytes: int, code: str) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError(code + "_invalid") from exc
    if len(encoded) > max_bytes:
        raise ValueError(code + "_too_large")
    return encoded.decode("utf-8")


def require_provider_status(value: Any) -> str:
    if not isinstance(value, str) or value not in WORKFLOW_PROVIDER_STATUSES:
        raise RuntimeError("cloudflare_workflow_status_unclassified")
    return value
