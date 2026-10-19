"""R4 research-only P-256 issuer-signature verifier.

No credential enrollment, Secure Enclave consent, replay cache, provider call,
ToolBroker admission, or runtime authorization. This module never signs.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

DOMAIN = b"CAPT:DecisionOfferingIssuerProof:v1\x00"
SCHEMA = "capt.decision-offering-issuer-proof.v1"
ALG = "ECDSA_P256_SHA256"
FIELDS = frozenset({
    "schemaVersion", "requestId", "issuerId", "keyId", "issuedAt",
    "expiresAt", "nonce", "commandFingerprint", "toolRequestDigest",
    "mainLedgerDigest", "offeringLedgerDigest", "action",
})
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
NONCE = re.compile(r"^[0-9a-f]{64}$")
IDENT = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
CLOCK = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")

@dataclass(frozen=True)
class TrustedIssuerKey:
    """Key entry MUST originate from a separately trusted enrollment registry."""
    key_id: str
    issuer_id: str
    public_key_pem: bytes
    purpose: str = "decision_offering_issue"
    revoked: bool = False

def signing_bytes(challenge: Mapping[str, Any]) -> bytes:
    body = json.dumps(
        challenge, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    return DOMAIN + body

def _parse_timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not CLOCK.fullmatch(value):
        raise ValueError("NONCANONICAL_TIMESTAMP")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

def _validate(challenge: Any) -> None:
    if not isinstance(challenge, dict) or frozenset(challenge) != FIELDS:
        raise ValueError("INVALID_CHALLENGE_SHAPE")
    if challenge.get("schemaVersion") != SCHEMA or challenge.get("action") != "issue_decision_offering":
        raise ValueError("WRONG_PROOF_PURPOSE")
    for key in ("requestId", "issuerId", "keyId"):
        if not isinstance(challenge[key], str) or not IDENT.fullmatch(challenge[key]):
            raise ValueError("INVALID_IDENTITY")
    if not isinstance(challenge["nonce"], str) or not NONCE.fullmatch(challenge["nonce"]):
        raise ValueError("INVALID_NONCE")
    for key in ("commandFingerprint", "toolRequestDigest", "mainLedgerDigest", "offeringLedgerDigest"):
        if not isinstance(challenge[key], str) or not DIGEST.fullmatch(challenge[key]):
            raise ValueError("INVALID_DIGEST")
    start = _parse_timestamp(challenge["issuedAt"])
    end = _parse_timestamp(challenge["expiresAt"])
    if end <= start or end-start > timedelta(seconds=60):
        raise ValueError("INVALID_PROOF_WINDOW")

def verify_signature_only(
    proof: Any,
    expected: Mapping[str, Any],
    registered_keys: Mapping[str, TrustedIssuerKey],
    *,
    now: datetime,
) -> dict[str, Any]:
    """Check cryptography/intent; caller-supplied inputs are NOT attested custody."""
    def outcome(reason: str, valid: bool = False):
        return {
            "reason": reason,
            "signature_valid_for_supplied_key": valid,
            "enrollment_custody_verified": False,
            "operator_presence_verified": False,
            "nonce_consumption_verified": False,
            "capability_verified": False,
            "dispatch_allowed": False,
            "completion_verified": False,
        }
    if not isinstance(now, datetime) or now.tzinfo is None:
        return outcome("CLOCK_NOT_TRUSTED")
    if not isinstance(proof, dict) or set(proof) != {"challenge", "algorithm", "signatureBase64"}:
        return outcome("PROOF_SHAPE_INVALID")
    if proof["algorithm"] != ALG:
        return outcome("UNSUPPORTED_SIGNATURE_ALGORITHM")
    challenge = proof["challenge"]
    try:
        _validate(challenge)
        _validate(dict(expected))
    except (TypeError, ValueError, KeyError):
        return outcome("CHALLENGE_INVALID")
    if challenge != dict(expected):
        return outcome("SIGNED_INTENT_MISMATCH")
    if not isinstance(registered_keys, Mapping):
        return outcome("TRUST_REGISTRY_INVALID")
    at = now.astimezone(timezone.utc)
    if at < _parse_timestamp(challenge["issuedAt"]) or at >= _parse_timestamp(challenge["expiresAt"]):
        return outcome("SIGNATURE_WINDOW_INACTIVE")
    key = registered_keys.get(challenge["keyId"])
    if not isinstance(key, TrustedIssuerKey):
        return outcome("UNKNOWN_ENROLLED_KEY")
    if key.revoked:
        return outcome("KEY_MARKED_REVOKED")
    if key.key_id != challenge["keyId"] or key.issuer_id != challenge["issuerId"]:
        return outcome("ENROLLMENT_IDENTITY_MISMATCH")
    if key.purpose != "decision_offering_issue":
        return outcome("KEY_PURPOSE_MISMATCH")
    try:
        pub = serialization.load_pem_public_key(key.public_key_pem)
        if not isinstance(pub, ec.EllipticCurvePublicKey) or not isinstance(pub.curve, ec.SECP256R1):
            return outcome("NON_P256_ENROLLED_KEY")
        encoded = proof["signatureBase64"]
        if not isinstance(encoded, str) or len(encoded) > 128:
            return outcome("MALFORMED_SIGNATURE")
        raw = base64.b64decode(encoded, validate=True)
        if not 8 <= len(raw) <= 80:
            return outcome("MALFORMED_SIGNATURE")
        pub.verify(raw, signing_bytes(challenge), ec.ECDSA(hashes.SHA256()))
    except (ValueError, TypeError, InvalidSignature, UnsupportedAlgorithm, binascii.Error):
        return outcome("SIGNATURE_INVALID")
    return outcome("SIGNATURE_VALID_BUT_NOT_AUTHORIZATION", True)
