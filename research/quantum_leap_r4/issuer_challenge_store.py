"""UPG-041 prototype: root-certified issuer enrollment and single-use challenges.

Experimental, isolated SQLite registry only. This is NOT RuntimeService
authentication, macOS hardware attestation, an approval, or ToolBroker admission.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Mapping, Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from research.quantum_leap_r4.issuer_signature import (
    TrustedIssuerKey, verify_signature_only,
)

ENROLL_DOMAIN = b"CAPT:UPG041:Enrollment:v1\x00"
REVOKE_DOMAIN = b"CAPT:UPG041:Revocation:v1\x00"
IDENT = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class ProofRefused(ValueError):
    pass


def _canonical(record: Mapping[str, Any]) -> bytes:
    return json.dumps(record, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ProofRefused("NAIVE_CLOCK")
    return value.astimezone(timezone.utc).replace(microsecond=0).strftime(FORMAT)


def _p256_public(pem: bytes):
    try:
        key = serialization.load_pem_public_key(pem)
    except (TypeError, ValueError) as exc:
        raise ProofRefused("INVALID_PINNED_PUBLIC_KEY") from exc
    if not isinstance(key, ec.EllipticCurvePublicKey) or not isinstance(key.curve, ec.SECP256R1):
        raise ProofRefused("NON_P256_PUBLIC_KEY")
    return key


class IssuerChallengeRegistry:
    """The caller must obtain the root key from *independently protected* config.

    A local SQLite root-digest pin only detects accidental mismatch; same-UID
    process compromise can change the DB and caller-config simultaneously.
    """

    def __init__(self, path: str, *, enrollment_root_pem: bytes,
                 main_store, offering_store,
                 clock: Callable[[], datetime] | None = None):
        import os
        if main_store is offering_store:
            raise ProofRefused("ISSUER_STORE_MUST_BE_ISOLATED")
        for other in (main_store, offering_store):
            if path != ":memory:" and other.path != ":memory:":
                same = Path(path).resolve() == Path(other.path).resolve()
                if Path(path).exists() and Path(other.path).exists():
                    same = same or os.path.samefile(path, other.path)
                if same:
                    raise ProofRefused("ISSUER_STORE_MUST_BE_ISOLATED")
        self._main_store = main_store
        self._offering_store = offering_store
        self._root = _p256_public(enrollment_root_pem)
        self._root_digest = "sha256:" + hashlib.sha256(enrollment_root_pem).hexdigest()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._db = sqlite3.connect(path, timeout=5, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA busy_timeout=5000")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.executescript(
            "CREATE TABLE IF NOT EXISTS root_pin ("
            " name TEXT PRIMARY KEY, digest TEXT NOT NULL);"
            "CREATE TABLE IF NOT EXISTS issuer_keys ("
            " key_id TEXT PRIMARY KEY, issuer_id TEXT NOT NULL,"
            " pem BLOB NOT NULL, purpose TEXT NOT NULL,"
            " revoked INTEGER NOT NULL DEFAULT 0);"
            "CREATE TABLE IF NOT EXISTS challenges ("
            " nonce TEXT PRIMARY KEY, key_id TEXT NOT NULL,"
            " body TEXT NOT NULL, consumed INTEGER NOT NULL DEFAULT 0,"
            " consumed_at TEXT,"
            " FOREIGN KEY(key_id) REFERENCES issuer_keys(key_id));"
        )
        self._db.execute("BEGIN IMMEDIATE")
        try:
            found = self._db.execute(
                "SELECT digest FROM root_pin WHERE name='root'"
            ).fetchone()
            if found is None:
                self._db.execute(
                    "INSERT INTO root_pin VALUES ('root',?)", (self._root_digest,)
                )
            elif found["digest"] != self._root_digest:
                raise ProofRefused("ROOT_KEY_PIN_MISMATCH")
            self._db.execute("COMMIT")
        except Exception:
            self._db.execute("ROLLBACK")
            raise

    def close(self):
        self._db.close()

    def _verify_root(self, domain: bytes, content: Mapping[str, Any],
                     signature_b64: str):
        if not isinstance(signature_b64, str) or len(signature_b64) > 128:
            raise ProofRefused("INVALID_ROOT_SIGNATURE")
        try:
            raw = base64.b64decode(signature_b64, validate=True)
            self._root.verify(raw, domain + _canonical(content), ec.ECDSA(hashes.SHA256()))
        except (ValueError, TypeError, InvalidSignature, binascii.Error) as exc:
            raise ProofRefused("INVALID_ROOT_SIGNATURE") from exc

    def enroll(self, certificate: dict, root_signature_base64: str):
        """No unauthenticated 'enroll public key' API: root signature mandatory."""
        if not isinstance(certificate, dict) or set(certificate) != {
            "schemaVersion", "issuerId", "keyId", "publicKeyPEM", "purpose"
        }:
            raise ProofRefused("INVALID_ENROLLMENT_CERTIFICATE")
        if certificate["schemaVersion"] != "capt.upg041.enrollment.v1":
            raise ProofRefused("INVALID_ENROLLMENT_SCHEMA")
        for key in ("issuerId", "keyId"):
            v=certificate[key]
            if not isinstance(v, str) or not IDENT.fullmatch(v):
                raise ProofRefused("INVALID_ENROLLMENT_ID")
        if certificate["purpose"] != "decision_offering_issue":
            raise ProofRefused("INVALID_ENROLLMENT_PURPOSE")
        if not isinstance(certificate["publicKeyPEM"],str):
            raise ProofRefused("INVALID_ENROLLMENT_KEY")
        pem=certificate["publicKeyPEM"].encode("ascii")
        _p256_public(pem)
        self._verify_root(ENROLL_DOMAIN,certificate,root_signature_base64)
        self._db.execute("BEGIN IMMEDIATE")
        try:
            self._db.execute(
                "INSERT INTO issuer_keys(key_id,issuer_id,pem,purpose) VALUES(?,?,?,?)",
                (certificate["keyId"],certificate["issuerId"],pem,certificate["purpose"])
            )
            self._db.execute("COMMIT")
        except Exception:
            self._db.execute("ROLLBACK")
            raise

    def revoke(self, key_id: str, root_signature_base64: str):
        """Revocation is root-signed and durable, but not an operator UI."""
        if not isinstance(key_id,str) or not IDENT.fullmatch(key_id):
            raise ProofRefused("INVALID_REVOCATION_ID")
        payload={"schemaVersion":"capt.upg041.revocation.v1","keyId":key_id}
        self._verify_root(REVOKE_DOMAIN,payload,root_signature_base64)
        self._db.execute("BEGIN IMMEDIATE")
        try:
            cursor=self._db.execute(
                "UPDATE issuer_keys SET revoked=1 WHERE key_id=? AND revoked=0",
                (key_id,)
            )
            if cursor.rowcount!=1:
                raise ProofRefused("UNKNOWN_OR_REVOKED_KEY")
            self._db.execute("COMMIT")
        except Exception:
            self._db.execute("ROLLBACK")
            raise

    def issue(self, *, issuer_id: str, key_id: str, request_id: str,
              command_fingerprint: str, tool_request_digest: str,
              main_store, offering_store) -> dict[str,str]:
        if main_store is not self._main_store or offering_store is not self._offering_store:
            raise ProofRefused("LEDGER_BINDING_MISMATCH")
        for ident in (issuer_id,key_id,request_id):
            if not isinstance(ident,str) or not IDENT.fullmatch(ident):
                raise ProofRefused("INVALID_ISSUE_IDENTITY")
        if any(not isinstance(d,str) or not DIGEST.fullmatch(d)
               for d in (command_fingerprint,tool_request_digest)):
            raise ProofRefused("INVALID_ISSUE_DIGEST")
        # Real CAPT EventStore instances provide both ledgers at issuance.
        main_head=main_store.head_chain()
        offer_head=offering_store.head_chain()
        if not DIGEST.fullmatch(main_head) or not DIGEST.fullmatch(offer_head):
            raise ProofRefused("UNKNOWN_WORLD_BASIS")
        self._db.execute("BEGIN IMMEDIATE")
        try:
            key=self._db.execute(
                "SELECT issuer_id,revoked FROM issuer_keys WHERE key_id=?",
                (key_id,)
            ).fetchone()
            if key is None or key["issuer_id"]!=issuer_id or key["revoked"]:
                raise ProofRefused("UNENROLLED_OR_REVOKED_ISSUER")
            start=self._clock()
            if not isinstance(start,datetime) or start.tzinfo is None:
                raise ProofRefused("UNTRUSTED_CLOCK")
            now=start.astimezone(timezone.utc).replace(microsecond=0)
            challenge={
                "schemaVersion":"capt.decision-offering-issuer-proof.v1",
                "requestId":request_id,"issuerId":issuer_id,"keyId":key_id,
                "issuedAt":_timestamp(now),
                "expiresAt":_timestamp(now+timedelta(seconds=60)),
                "nonce":secrets.token_hex(32),
                "commandFingerprint":command_fingerprint,
                "toolRequestDigest":tool_request_digest,
                "mainLedgerDigest":main_head,"offeringLedgerDigest":offer_head,
                "action":"issue_decision_offering",
            }
            self._db.execute(
                "INSERT INTO challenges(nonce,key_id,body) VALUES(?,?,?)",
                (challenge["nonce"],key_id,_canonical(challenge).decode("utf-8"))
            )
            self._db.execute("COMMIT")
            return challenge
        except Exception:
            self._db.execute("ROLLBACK")
            raise

    def consume(self, proof: dict, *, main_store, offering_store) -> dict[str,Any]:
        """Atomic replay refusal, not a CAPT capability or approval decision."""
        if main_store is not self._main_store or offering_store is not self._offering_store:
            raise ProofRefused("LEDGER_BINDING_MISMATCH")
        if not isinstance(proof,dict) or not isinstance(proof.get("challenge"),dict):
            raise ProofRefused("INVALID_SIGNED_PROOF")
        nonce=proof["challenge"].get("nonce")
        if not isinstance(nonce,str) or not re.fullmatch("[0-9a-f]{64}",nonce):
            raise ProofRefused("INVALID_NONCE")
        self._db.execute("BEGIN IMMEDIATE")
        try:
            row=self._db.execute(
                "SELECT body,key_id,consumed FROM challenges WHERE nonce=?",(nonce,)
            ).fetchone()
            if row is None or row["consumed"]:
                raise ProofRefused("UNKNOWN_OR_CONSUMED_NONCE")
            expected=json.loads(row["body"])
            entry=self._db.execute(
                "SELECT issuer_id,pem,purpose,revoked FROM issuer_keys WHERE key_id=?",
                (row["key_id"],)
            ).fetchone()
            if entry is None:
                raise ProofRefused("ENROLLMENT_MISSING")
            registered={row["key_id"]:TrustedIssuerKey(
                row["key_id"],entry["issuer_id"],entry["pem"],
                entry["purpose"],bool(entry["revoked"]),
            )}
            now=self._clock()
            verdict=verify_signature_only(proof,expected,registered,now=now)
            if not verdict["signature_valid_for_supplied_key"]:
                raise ProofRefused("SIGNED_CHALLENGE_REFUSED:"+verdict["reason"])
            if (expected["mainLedgerDigest"] != main_store.head_chain()
                or expected["offeringLedgerDigest"] != offering_store.head_chain()):
                raise ProofRefused("WORLD_OR_POLICY_LEDGER_CHANGED")
            self._db.execute(
                "UPDATE challenges SET consumed=1,consumed_at=? WHERE nonce=? AND consumed=0",
                (_timestamp(now),nonce)
            )
            self._db.execute("COMMIT")
            return {
                "reason":"SIGNED_CHALLENGE_CONSUMED_NOT_AUTHORIZATION",
                "signatureValid":True,"singleUseNonceConsumed":True,
                "rootCertificateVerifiedAgainstSuppliedRoot":True,
                "rootCustodyIndependentlyVerified":False,
                "operatorPresenceVerified":False,
                "runtimeAdmissionVerified":False,
                "dispatchAllowed":False,"completionVerified":False,
            }
        except Exception:
            self._db.execute("ROLLBACK")
            raise
