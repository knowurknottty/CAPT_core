"""Cryptographic separation between Node transport identity and execution authority."""

from __future__ import annotations

import base64
from dataclasses import replace

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .identity import CapabilityAuthorityIdentity
from .protocol import canonical_json
from .types import OperationCapability


def capability_signing_payload(capability: OperationCapability) -> dict:
    return {
        "capabilityId": capability.capability_id,
        "botId": capability.bot_id,
        "missionId": capability.mission_id,
        "taskId": capability.task_id,
        "controllerId": capability.controller_id,
        "nodeId": capability.node_id,
        "permittedOperations": sorted(capability.permitted_operations),
        "filesystemRoots": list(capability.filesystem_roots),
        "issuedAt": capability.issued_at.isoformat(),
        "expiresAt": capability.expires_at.isoformat(),
        "authorityIssuerId": capability.authority_issuer_id,
    }


def sign_capability(
    capability: OperationCapability, authority: CapabilityAuthorityIdentity
) -> OperationCapability:
    unsigned = replace(
        capability,
        authority_issuer_id=authority.authority_id,
        authority_signature=None,
    )
    signature = authority.sign(canonical_json(capability_signing_payload(unsigned)))
    return replace(
        unsigned,
        authority_signature=base64.b64encode(signature).decode("ascii"),
    )


def verify_capability_authority(
    capability: OperationCapability,
    authority_issuers: dict[str, bytes],
) -> None:
    issuer_id = capability.authority_issuer_id
    signature = capability.authority_signature
    if not issuer_id or not signature:
        raise PermissionError("capability_authority_signature_missing")
    public = authority_issuers.get(issuer_id)
    if public is None:
        raise PermissionError("capability_authority_issuer_untrusted")
    try:
        decoded = base64.b64decode(signature, validate=True)
        Ed25519PublicKey.from_public_bytes(public).verify(
            decoded,
            canonical_json(capability_signing_payload(capability)),
        )
    except (InvalidSignature, ValueError) as exc:
        raise PermissionError("capability_authority_signature_invalid") from exc
