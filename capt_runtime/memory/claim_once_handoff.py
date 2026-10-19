"""Optional durable, claim-once handoff inbox adapted from ai-memory ideas.

This is a storage primitive, NOT an authentication or authorization endpoint.
Only a trusted CAPT RuntimeService adapter may call offer/claim/revoke after
independently validating the authenticated principal, permitted resource,
provenance, and HumanApproval requirements.

No generated memory text is admitted here: only opaque source digests and
human-readable, nonsecret source references. The existing EventStore remains
the sole CAPT admission/authority ledger. No background actions.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import re
import sqlite3
import time
from typing import Callable, Iterator

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,126}$")
_DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")


class HandoffRefused(ValueError):
    """Handoff refused without affecting durable state."""


@dataclass(frozen=True)
class HandoffReceipt:
    handoff_id: str
    source_digest: str
    target_principal: str
    claimed_by: str
    claimed_at: int
    replayed: bool = False


def _ident(label: str, value: object) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise HandoffRefused("INVALID_" + label.upper())
    return value


class ClaimOnceHandoffStore:
    """SQLite-backed atomic one-time claim, without CAPT policy authority."""

    def __init__(self, path: str | Path, *, clock: Callable[[], float] = time.time):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        with self._conn() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS handoff (
               handoff_id TEXT PRIMARY KEY,
               issuer TEXT NOT NULL,
               target_principal TEXT NOT NULL,
               source_digest TEXT NOT NULL,
               created_at INTEGER NOT NULL,
               expires_at INTEGER NOT NULL,
               status TEXT NOT NULL CHECK (status IN ('open','claimed','revoked')),
               claimed_by TEXT,
               claim_key TEXT,
               claimed_at INTEGER,
               CHECK ((status='claimed' AND claimed_by IS NOT NULL AND claim_key IS NOT NULL
                        AND claimed_at IS NOT NULL)
                       OR (status!='claimed' AND claimed_by IS NULL AND claim_key IS NULL
                        AND claimed_at IS NULL))
            )""")

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        # The trusted host is responsible for its private filesystem root.
        db = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
        try:
            os.chmod(self.path, 0o600)
            db.execute("PRAGMA busy_timeout=5000")
            yield db
        finally:
            db.close()

    def offer(
        self, *,
        handoff_id: str,
        issuer: str,
        target_principal: str,
        source_digest: str,
        ttl_seconds: int = 3600,
    ) -> str:
        _ident("handoff_id", handoff_id)
        _ident("issuer", issuer)
        _ident("target_principal", target_principal)
        if not isinstance(source_digest,str) or not _DIGEST.fullmatch(source_digest):
            raise HandoffRefused("INVALID_SOURCE_DIGEST")
        if type(ttl_seconds) is not int or not 60 <= ttl_seconds <= 86400:
            raise HandoffRefused("INVALID_EXPIRY")
        now=int(self.clock())
        with self._conn() as db:
            db.execute("BEGIN IMMEDIATE")
            old=db.execute(
                "SELECT issuer,target_principal,source_digest,created_at,expires_at,status "
                "FROM handoff WHERE handoff_id=?", (handoff_id,)
            ).fetchone()
            if old is not None:
                # Same ID with different target/payload MUST NOT silently redirect.
                if old[:3]!=(issuer,target_principal,source_digest):
                    raise HandoffRefused("HANDOFF_ID_CONFLICT")
                return "already_exists"
            db.execute(
                "INSERT INTO handoff(handoff_id,issuer,target_principal,source_digest,"
                "created_at,expires_at,status) VALUES(?,?,?,?,?,?,?)",
                (handoff_id,issuer,target_principal,source_digest,now,now+ttl_seconds,"open")
            )
            db.execute("COMMIT")
            return "created"

    def claim(
        self, *, handoff_id: str, principal: str, claim_key: str,
        expected_source_digest: str,
    ) -> HandoffReceipt:
        _ident("handoff_id",handoff_id)
        _ident("principal",principal)
        _ident("claim_key",claim_key)
        if not isinstance(expected_source_digest,str) or not _DIGEST.fullmatch(expected_source_digest):
            raise HandoffRefused("INVALID_SOURCE_DIGEST")
        now=int(self.clock())
        with self._conn() as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute(
                "SELECT target_principal,source_digest,expires_at,status,claimed_by,"
                "claim_key,claimed_at FROM handoff WHERE handoff_id=?",(handoff_id,)
            ).fetchone()
            if row is None:
                raise HandoffRefused("HANDOFF_NOT_FOUND")
            target,digest,expires,status,by,key,claimed_at=row
            if target != principal:
                raise HandoffRefused("HANDOFF_WRONG_PRINCIPAL")
            if digest != expected_source_digest:
                raise HandoffRefused("HANDOFF_SOURCE_CHANGED")
            if status=="claimed":
                if by==principal and key==claim_key:
                    return HandoffReceipt(handoff_id,digest,target,by,claimed_at,True)
                raise HandoffRefused("HANDOFF_ALREADY_CLAIMED")
            if status=="revoked":
                raise HandoffRefused("HANDOFF_REVOKED")
            if expires<=now:
                raise HandoffRefused("HANDOFF_EXPIRED")
            db.execute(
                "UPDATE handoff SET status='claimed',claimed_by=?,claim_key=?,claimed_at=? "
                "WHERE handoff_id=? AND status='open'",(principal,claim_key,now,handoff_id)
            )
            db.execute("COMMIT")
            return HandoffReceipt(handoff_id,digest,target,principal,now,False)

    def revoke(self, *, handoff_id: str, issuer: str) -> bool:
        _ident("handoff_id",handoff_id)
        _ident("issuer",issuer)
        with self._conn() as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT issuer,status FROM handoff WHERE handoff_id=?",(handoff_id,)).fetchone()
            if row is None or row[0]!=issuer:
                raise HandoffRefused("HANDOFF_REVOKE_ISSUER_MISMATCH")
            if row[1]=="claimed":
                raise HandoffRefused("HANDOFF_ALREADY_CLAIMED")
            if row[1]=="revoked":
                return False
            db.execute("UPDATE handoff SET status='revoked' WHERE handoff_id=?",(handoff_id,))
            db.execute("COMMIT")
            return True

    def inspect(self, handoff_id: str) -> dict:
        _ident("handoff_id",handoff_id)
        with self._conn() as db:
            row=db.execute(
                "SELECT handoff_id,issuer,target_principal,source_digest,created_at,expires_at,"
                "status,claimed_by,claimed_at FROM handoff WHERE handoff_id=?",(handoff_id,)
            ).fetchone()
        if row is None: raise HandoffRefused("HANDOFF_NOT_FOUND")
        keys=("handoffId","issuer","targetPrincipal","sourceDigest","createdAt",
              "expiresAt","status","claimedBy","claimedAt")
        return dict(zip(keys,row))
