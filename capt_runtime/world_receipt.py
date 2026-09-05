"""THE WORLD RECEIPT protocol primitives.

The EventStore records CAPT's decisions. A WorldReceipt is different: it is
proof rooted at the mutated target and bound to the exact durable EffectIntent.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from .contracts import digest, require
from .errors import AuthorityViolation, IntegrityViolation


def _stable_id(prefix: str, material: str) -> str:
    return prefix + hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def effect_intent_id(idempotency_key: str) -> str:
    return _stable_id("effect-intent-", idempotency_key)


def world_receipt_id(intent_digest: str, observed_state_digest: str) -> str:
    return _stable_id("world-receipt-", intent_digest + observed_state_digest)


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AuthorityViolation("WORLD_RECEIPT_TIMESTAMP_INVALID") from exc
    if parsed.tzinfo is None:
        raise AuthorityViolation("WORLD_RECEIPT_TIMESTAMP_TIMEZONE_REQUIRED")
    return parsed.astimezone(timezone.utc)


def timestamp_before(left: str, right: str) -> bool:
    """Compare schema timestamps by instant, never lexicographically."""
    return _timestamp(left) < _timestamp(right)


def timestamp_at_or_before(left: str, right: str) -> bool:
    return _timestamp(left) <= _timestamp(right)


def receipt_required(descriptor: dict[str, Any], operation: str) -> bool:
    return operation in set(descriptor.get("worldReceiptOperations") or [])


def build_effect_intent(
    request: dict[str, Any], *, principal_id: str, preparation: dict[str, Any],
    expires_at: str,
) -> dict[str, Any]:
    target = str(preparation.get("targetIdentity") or "")
    offered_target = request.get("targetIdentity")
    if offered_target is not None and str(offered_target) != target:
        raise AuthorityViolation("WORLD_RECEIPT_TARGET_IDENTITY_MISMATCH")
    basis = str(preparation.get("basisVersion") or "")
    atomic_domain = str(preparation.get("atomicDomain") or "")
    coordination = str(preparation.get("coordinationMode") or "")
    targets = preparation.get("targetIdentities") or ([target] if target else [])
    if not target or not basis or not atomic_domain:
        raise AuthorityViolation("WORLD_RECEIPT_PREPARATION_INCOMPLETE")
    if coordination == "atomic" and len(set(map(str, targets))) != 1:
        raise AuthorityViolation("WORLD_RECEIPT_FAKE_DISTRIBUTED_ATOMICITY")
    if coordination not in {"atomic", "staged", "compensating", "escrow"}:
        raise AuthorityViolation("WORLD_RECEIPT_COORDINATION_MODE_REQUIRED")

    intent = {
        "schemaVersion": "1.0.0",
        "effectIntentId": effect_intent_id(request["idempotencyKey"]),
        "principalId": principal_id,
        "operation": request["operation"],
        "payloadDigest": digest(request["arguments"]),
        "basisVersion": basis,
        "grantId": request.get("grantId"),
        "leaseId": request.get("leaseId"),
        "approvalRefs": list(preparation.get("approvalRefs") or []),
        "targetIdentity": target,
        "expiresAt": expires_at,
        "idempotencyKey": request["idempotencyKey"],
        "atomicDomain": atomic_domain,
        "coordinationMode": coordination,
        "rollbackStrategy": str(preparation.get("rollbackStrategy") or "none"),
        "reconciliationStrategy": str(
            preparation.get("reconciliationStrategy") or "target_receipt"
        ),
        "reversalHandle": preparation.get("reversalHandle"),
        "receiptSpec": deepcopy(preparation.get("receiptSpec") or {}),
        "intentDigest": "sha256:" + "0" * 64,
    }
    if timestamp_at_or_before(intent["expiresAt"], request["requestedAt"]):
        raise AuthorityViolation("WORLD_RECEIPT_INTENT_EXPIRED_AT_PREPARE")
    digest_material = deepcopy(intent)
    digest_material.pop("intentDigest")
    intent["intentDigest"] = digest(digest_material)
    require("EffectIntent", intent)
    return intent


def verify_world_receipt(
    intent: dict[str, Any], receipt: dict[str, Any]
) -> None:
    require("EffectIntent", intent)
    require("WorldReceipt", receipt)
    checks = {
        "receiptId": world_receipt_id(
            intent["intentDigest"], intent["receiptSpec"]["expectedPostStateDigest"]
        ),
        "effectIntentId": intent["effectIntentId"],
        "intentDigest": intent["intentDigest"],
        "targetIdentity": intent["targetIdentity"],
        "receiptKind": intent["receiptSpec"]["receiptKind"],
        "receiptLocator": intent["receiptSpec"]["locator"],
        "observedStateDigest": intent["receiptSpec"]["expectedPostStateDigest"],
        "commitState": "committed",
        "reversalHandle": intent.get("reversalHandle"),
    }
    for key, expected in checks.items():
        if receipt.get(key) != expected:
            raise IntegrityViolation(
                f"WORLD_RECEIPT_{key.upper()}_MISMATCH: "
                f"expected {expected!r}, observed {receipt.get(key)!r}"
            )


def receipt_side_effect_identity(receipt: dict[str, Any]) -> str:
    """Bounded identity suitable for ToolExecution/capability settlement."""
    require("WorldReceipt", receipt)
    return json.dumps(
        {
            "receiptId": receipt["receiptId"],
            "intentDigest": receipt["intentDigest"],
            "observedStateDigest": receipt["observedStateDigest"],
            "commitState": receipt["commitState"],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
