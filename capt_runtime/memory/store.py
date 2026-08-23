"""In-ledger CAPT memory store (M1-memory, ADR-DT-M1-MEM-001).

This is the AUTHORITATIVE memory persistence for the runtime trigger system.
Records carry full provenance, trust, verification status, sensitivity, and
consent. The store is the single source of truth for memory; drivers and the
desktop never write here directly.

The store is intentionally simple (SQLite-backed, same ledger family as the
event store) so it can be wired into the runtime transaction boundary. It does
NOT implement the disconnected capt_solo.memory engine; it is a focused,
runtime-owned record store sufficient for the mandatory trigger contract.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from typing import Any, Dict, List, Optional

from ..contracts import require
from ..state_security import (
    AtRestProtector,
    MAX_MEMORY_CONTENT_BYTES,
    harden_sqlite_path,
    validate_persisted_text,
)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class MemoryRecord:
    """A stored memory record with governance metadata."""

    def __init__(
        self,
        *,
        record_id: str,
        memory_class: str,
        owner: str,
        source: str,
        provenance: str,
        trust: str,
        verification_status: str,
        sensitivity: str,
        consent: str,
        content: str,
        created_at: Optional[str] = None,
        last_verified_at: Optional[str] = None,
        expires_at: Optional[str] = None,
        stale: bool = False,
        conflict_state: Optional[str] = None,
        downstream_use_restriction: Optional[str] = None,
    ) -> None:
        self.record_id = record_id
        self.memory_class = memory_class
        self.owner = owner
        self.source = source
        self.provenance = provenance
        self.trust = trust
        self.verification_status = verification_status
        self.sensitivity = sensitivity
        self.consent = consent
        self.content = content
        self.created_at = created_at or _now_iso()
        self.last_verified_at = last_verified_at
        self.expires_at = expires_at
        self.stale = stale
        self.conflict_state = conflict_state
        self.downstream_use_restriction = downstream_use_restriction
        self.digest = self._digest()

    def _digest(self) -> str:
        canon = json.dumps(
            {
                "record_id": self.record_id,
                "memory_class": self.memory_class,
                "owner": self.owner,
                "source": self.source,
                "provenance": self.provenance,
                "trust": self.trust,
                "verification_status": self.verification_status,
                "sensitivity": self.sensitivity,
                "consent": self.consent,
                "content": self.content,
                "stale": self.stale,
                "conflict_state": self.conflict_state,
            },
            sort_keys=True,
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(canon).hexdigest()

    def to_record_dict(self) -> Dict[str, Any]:
        """Return the contract-shaped MemoryRecord (no raw content)."""
        return {
            "recordId": self.record_id,
            "memoryClass": self.memory_class,
            "owner": self.owner,
            "source": self.source,
            "provenance": self.provenance,
            "trust": self.trust,
            "verificationStatus": self.verification_status,
            "sensitivity": self.sensitivity,
            "consent": self.consent,
            "createdAt": self.created_at,
            "lastVerifiedAt": self.last_verified_at,
            "expiresAt": self.expires_at,
            "digest": self.digest,
            "retrievalScore": 0.0,
            "retrievalReason": "",
            "stale": self.stale,
            "conflictState": self.conflict_state,
            "downstreamUseRestriction": self.downstream_use_restriction,
        }

    def with_retrieval(self, score: float, reason: str) -> Dict[str, Any]:
        d = self.to_record_dict()
        d["retrievalScore"] = score
        d["retrievalReason"] = reason
        return d


class MemoryStore:
    """SQLite-backed memory record store owned by CAPT Runtime."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self._lock = __import__("threading").Lock()
        harden_sqlite_path(db_path)
        self._protector = AtRestProtector.for_path(db_path)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        if db_path != ":memory:":
            self._migrate_plaintext_content()
            harden_sqlite_path(db_path)

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_records (
                record_id TEXT PRIMARY KEY,
                memory_class TEXT NOT NULL,
                owner TEXT NOT NULL,
                source TEXT NOT NULL,
                provenance TEXT NOT NULL,
                trust TEXT NOT NULL,
                verification_status TEXT NOT NULL,
                sensitivity TEXT NOT NULL,
                consent TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_verified_at TEXT,
                expires_at TEXT,
                stale INTEGER NOT NULL DEFAULT 0,
                conflict_state TEXT,
                downstream_use_restriction TEXT,
                digest TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def _content_context(self, record_id: str) -> str:
        return "memory_records.content:%s" % record_id

    def _migrate_plaintext_content(self) -> None:
        rows = self._conn.execute(
            "SELECT record_id, content FROM memory_records"
        ).fetchall()
        changed = False
        for row in rows:
            stored = str(row["content"])
            if self._protector.is_sealed(stored):
                self._protector.open_text(
                    stored, context=self._content_context(str(row["record_id"]))
                )
                continue
            validate_persisted_text(
                stored, field="MEMORY_CONTENT", max_bytes=MAX_MEMORY_CONTENT_BYTES
            )
            sealed = self._protector.seal_text(
                stored, context=self._content_context(str(row["record_id"]))
            )
            self._conn.execute(
                "UPDATE memory_records SET content = ? WHERE record_id = ?",
                (sealed, row["record_id"]),
            )
            changed = True
        if changed:
            self._conn.commit()
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            self._conn.execute("VACUUM")

    def store(self, rec: MemoryRecord) -> None:
        validate_persisted_text(
            rec.content, field="MEMORY_CONTENT", max_bytes=MAX_MEMORY_CONTENT_BYTES
        )
        stored_content = self._protector.seal_text(
            rec.content, context=self._content_context(rec.record_id)
        )
        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO memory_records
                (record_id, memory_class, owner, source, provenance, trust,
                 verification_status, sensitivity, consent, content, created_at,
                 last_verified_at, expires_at, stale, conflict_state,
                 downstream_use_restriction, digest)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    rec.record_id,
                    rec.memory_class,
                    rec.owner,
                    rec.source,
                    rec.provenance,
                    rec.trust,
                    rec.verification_status,
                    rec.sensitivity,
                    rec.consent,
                    stored_content,
                    rec.created_at,
                    rec.last_verified_at,
                    rec.expires_at,
                    1 if rec.stale else 0,
                    rec.conflict_state,
                    rec.downstream_use_restriction,
                    rec.digest,
                ),
            )
            self._conn.commit()

    def get(self, record_id: str) -> Optional[MemoryRecord]:
        row = self._conn.execute(
            "SELECT * FROM memory_records WHERE record_id = ?", (record_id,)
        ).fetchone()
        return self._row_to_record(row) if row else None

    def _row_to_record(self, row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            record_id=row["record_id"],
            memory_class=row["memory_class"],
            owner=row["owner"],
            source=row["source"],
            provenance=row["provenance"],
            trust=row["trust"],
            verification_status=row["verification_status"],
            sensitivity=row["sensitivity"],
            consent=row["consent"],
            content=self._protector.open_text(
                row["content"], context=self._content_context(str(row["record_id"]))
            ),
            created_at=row["created_at"],
            last_verified_at=row["last_verified_at"],
            expires_at=row["expires_at"],
            stale=bool(row["stale"]),
            conflict_state=row["conflict_state"],
            downstream_use_restriction=row["downstream_use_restriction"],
        )

    def query(
        self,
        *,
        classes: Optional[List[str]] = None,
        project_scope: Optional[str] = None,
        trust_threshold: float = 0.0,
        consent_scope: Optional[str] = None,
        sensitivity_allowance: Optional[str] = None,
        limit: int = 20,
        exclude_record_ids: Optional[set] = None,
        bypass_governance: bool = False,
    ) -> List[MemoryRecord]:
        """Retrieve candidate records.

        When bypass_governance is False (default), consent/sensitivity filtering
        is enforced here. When True, ALL records matching the class filter are
        returned so the caller (_select_records) can apply consent/sensitivity
        filtering in Python and report the exclusions as visible (not silently
        dropped). This keeps consent/sensitivity exclusions auditable."""
        sql = "SELECT * FROM memory_records WHERE 1=1"
        params: List[Any] = []
        if classes:
            sql += " AND memory_class IN (%s)" % ",".join("?" * len(classes))
            params.extend(classes)
        if not bypass_governance:
            if consent_scope:
                sql += " AND consent = ?"
                params.append(consent_scope)
            if sensitivity_allowance:
                # Lower sensitivity rank allowed. Map ordering: public < project < user < secret.
                order = {"public": 0, "project": 1, "user": 2, "secret": 3}
                allowed = [
                    k for k, v in order.items() if v <= order.get(sensitivity_allowance, 3)
                ]
                sql += " AND sensitivity IN (%s)" % ",".join("?" * len(allowed))
                params.extend(allowed)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        out: List[MemoryRecord] = []
        for row in rows:
            rec = self._row_to_record(row)
            if exclude_record_ids and rec.record_id in exclude_record_ids:
                continue
            out.append(rec)
        return out

    def all_record_ids(self) -> List[str]:
        return [
            r["record_id"]
            for r in self._conn.execute("SELECT record_id FROM memory_records").fetchall()
        ]

    def close(self) -> None:
        self._conn.close()
        harden_sqlite_path(self.db_path)
