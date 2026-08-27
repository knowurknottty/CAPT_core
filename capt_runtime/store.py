"""Transactional state store, event ledger, and outbox (ADR-0104, ADR-0105).

Single SQLite database, single transaction per command. Aggregate snapshot,
durable event, and outbox row are committed together or not at all. Dispatch
happens strictly after commit, driven by the outbox — never inline.

Ordering is by (stream_id, stream_version) within a stream and by
global_sequence across streams. Timestamps are descriptive only (ADR-0106).
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from .contracts import canonical_json, digest, require
from .state_security import AtRestProtector, harden_sqlite_path
from .errors import (
    ConcurrencyConflict,
    IdempotencyConflict,
    IntegrityViolation,
    NotFound,
)

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS events (
    global_sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id        TEXT NOT NULL UNIQUE,
    stream_id       TEXT NOT NULL,
    stream_version  INTEGER NOT NULL,
    event_type      TEXT NOT NULL,
    schema_version  TEXT NOT NULL,
    envelope_json   TEXT NOT NULL,
    payload_digest  TEXT NOT NULL,
    chain_digest    TEXT NOT NULL,
    UNIQUE (stream_id, stream_version)
);

CREATE TABLE IF NOT EXISTS aggregates (
    stream_id   TEXT PRIMARY KEY,
    kind        TEXT NOT NULL,
    version     INTEGER NOT NULL,
    state_json  TEXT NOT NULL,
    state_digest TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS outbox (
    event_id        TEXT PRIMARY KEY,
    global_sequence INTEGER NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('pending','dispatched')),
    attempts        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS idempotency (
    idempotency_key      TEXT PRIMARY KEY,
    operation_fingerprint TEXT NOT NULL,
    command_id           TEXT NOT NULL,
    result_json          TEXT NOT NULL,
    global_sequence      INTEGER
);

CREATE TABLE IF NOT EXISTS checkpoints (
    checkpoint_id  TEXT PRIMARY KEY,
    manifest_json  TEXT NOT NULL,
    integrity_digest TEXT NOT NULL,
    global_sequence INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS security_rejections (
    rejection_id    TEXT PRIMARY KEY,
    timestamp       TEXT NOT NULL,
    rejection_kind  TEXT NOT NULL,
    source_ip       TEXT,
    actor_id        TEXT,
    details_json    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_stream ON events (stream_id, stream_version);
CREATE INDEX IF NOT EXISTS idx_outbox_pending ON outbox (status, global_sequence);
CREATE INDEX IF NOT EXISTS idx_security_rejections ON security_rejections (rejection_kind, timestamp);
"""

GENESIS_CHAIN = "sha256:" + "0" * 64


def chain_next(previous: str, payload_digest: str, event_id: str) -> str:
    """Hash-chain link. Detects reordering, insertion, and truncation."""
    material = "%s|%s|%s" % (previous, payload_digest, event_id)
    return "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


class AppendRequest(object):
    """One event to append inside a command transaction."""

    __slots__ = ("stream_id", "kind", "expected_version", "envelope", "state")

    def __init__(
        self,
        stream_id: str,
        kind: str,
        expected_version: int,
        envelope: Dict[str, Any],
        state: Dict[str, Any],
    ) -> None:
        self.stream_id = stream_id
        self.kind = kind
        self.expected_version = expected_version
        self.envelope = envelope
        self.state = state


class EventStore(object):
    """Transactional aggregate + ledger + outbox store."""

    def __init__(self, path: str) -> None:
        self.path = path
        if path != ":memory:":
            parent = Path(path).parent
            if not parent.exists():
                parent.mkdir(parents=True, exist_ok=True)
                try:
                    os.chmod(parent, 0o700)
                except OSError:
                    pass
        self._lock = threading.RLock()
        self._protector = AtRestProtector.for_path(path)
        self._conn = sqlite3.connect(
            path, isolation_level=None, check_same_thread=False, timeout=5.0
        )
        if path != ":memory:":
            self._harden_permissions()
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.row_factory = sqlite3.Row
        # Two runtime processes can open an empty ledger concurrently before
        # one has installed WAL/schema. SQLite serializes this initialization;
        # retry only the transient lock, never a SQL/schema failure.
        for attempt in range(20):
            try:
                self._conn.executescript(SCHEMA_SQL)
                break
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower() or attempt == 19:
                    self._conn.close()
                    raise
                time.sleep(0.05 * (attempt + 1))
        if path != ":memory:":
            self._migrate_plaintext_json()
            self._harden_permissions()
        self._subscribers: List[Callable[[Dict[str, Any]], None]] = []

    def _harden_permissions(self) -> None:
        """Restrict the SQLite database and sidecars to the owning user."""
        if self.path == ":memory:":
            return
        db = Path(self.path)
        for target in (db, db.with_name(db.name + "-wal"), db.with_name(db.name + "-shm")):
            if target.exists():
                try:
                    os.chmod(target, 0o600)
                except OSError:
                    pass

    @staticmethod
    def _json_context(table: str, column: str, key: str) -> str:
        return "%s.%s:%s" % (table, column, key)

    def _seal_json(self, value: Dict[str, Any], *, table: str, column: str, key: str) -> str:
        return self._protector.seal_text(
            canonical_json(value), context=self._json_context(table, column, key)
        )

    def _open_json(self, stored: str, *, table: str, column: str, key: str) -> Dict[str, Any]:
        clear = self._protector.open_text(
            stored, context=self._json_context(table, column, key)
        )
        return json.loads(clear)

    def _migrate_plaintext_json(self) -> None:
        specs = (
            ("events", "event_id", "envelope_json"),
            ("aggregates", "stream_id", "state_json"),
            ("idempotency", "idempotency_key", "result_json"),
            ("checkpoints", "checkpoint_id", "manifest_json"),
            ("security_rejections", "rejection_id", "details_json"),
        )
        changed = False
        with self.transaction() as conn:
            for table, key_col, value_col in specs:
                rows = conn.execute(
                    "SELECT %s, %s FROM %s" % (key_col, value_col, table)
                ).fetchall()
                for row in rows:
                    stored = str(row[value_col])
                    if not stored:
                        continue
                    context = self._json_context(table, value_col, str(row[key_col]))
                    if self._protector.is_sealed(stored):
                        self._protector.open_text(stored, context=context)
                        continue
                    sealed = self._protector.seal_text(
                        stored,
                        context=context,
                    )
                    conn.execute(
                        "UPDATE %s SET %s = ? WHERE %s = ?" % (table, value_col, key_col),
                        (sealed, row[key_col]),
                    )
                    changed = True
        if changed:
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            self._conn.execute("VACUUM")

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        self._conn.close()

    def subscribe(self, handler: Callable[[Dict[str, Any]], None]) -> None:
        """Register a post-commit subscriber. Called only from dispatch()."""
        self._subscribers.append(handler)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """IMMEDIATE transaction: write lock taken up front, no upgrade races."""
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            self._conn.execute("COMMIT")

    # -- reads -------------------------------------------------------------

    def aggregate_version(self, stream_id: str) -> int:
        row = self._conn.execute(
            "SELECT version FROM aggregates WHERE stream_id = ?", (stream_id,)
        ).fetchone()
        return int(row["version"]) if row else 0

    def load_state(self, stream_id: str) -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            "SELECT stream_id, state_json FROM aggregates WHERE stream_id = ?", (stream_id,)
        ).fetchone()
        return self._open_json(
            row["state_json"], table="aggregates", column="state_json", key=row["stream_id"]
        ) if row else None

    def require_state(self, stream_id: str) -> Dict[str, Any]:
        state = self.load_state(stream_id)
        if state is None:
            raise NotFound("no aggregate at stream %s" % stream_id)
        return state

    def head_sequence(self) -> int:
        row = self._conn.execute("SELECT MAX(global_sequence) AS m FROM events").fetchone()
        return int(row["m"]) if row and row["m"] is not None else 0

    def head_chain(self) -> str:
        row = self._conn.execute(
            "SELECT chain_digest FROM events ORDER BY global_sequence DESC LIMIT 1"
        ).fetchone()
        return row["chain_digest"] if row else GENESIS_CHAIN

    def read_events(self, after_sequence: int = 0) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT event_id, envelope_json FROM events WHERE global_sequence > ? "
            "ORDER BY global_sequence ASC",
            (after_sequence,),
        ).fetchall()
        return [self._open_json(
            r["envelope_json"], table="events", column="envelope_json", key=r["event_id"]
        ) for r in rows]

    def read_recent_events(
        self, after_sequence: int = 0, limit: int = 250
    ) -> List[Dict[str, Any]]:
        """Return the newest bounded event window in chronological order."""
        bounded = max(0, int(limit))
        if bounded == 0:
            return []
        rows = self._conn.execute(
            "SELECT event_id, envelope_json FROM events WHERE global_sequence > ? "
            "ORDER BY global_sequence DESC LIMIT ?",
            (after_sequence, bounded),
        ).fetchall()
        decoded = [self._open_json(
            r["envelope_json"], table="events", column="envelope_json", key=r["event_id"]
        ) for r in rows]
        decoded.reverse()
        return decoded

    def read_stream(self, stream_id: str) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT event_id, envelope_json FROM events WHERE stream_id = ? "
            "ORDER BY stream_version ASC",
            (stream_id,),
        ).fetchall()
        return [self._open_json(
            r["envelope_json"], table="events", column="envelope_json", key=r["event_id"]
        ) for r in rows]

    def all_aggregates(self) -> List[Tuple[str, str, int]]:
        rows = self._conn.execute(
            "SELECT stream_id, kind, version FROM aggregates ORDER BY stream_id"
        ).fetchall()
        return [(r["stream_id"], r["kind"], int(r["version"])) for r in rows]

    def pending_outbox(self) -> List[str]:
        rows = self._conn.execute(
            "SELECT event_id FROM outbox WHERE status = 'pending' "
            "ORDER BY global_sequence ASC"
        ).fetchall()
        return [r["event_id"] for r in rows]

    def find_idempotent(self, key: str) -> Optional[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM idempotency WHERE idempotency_key = ?", (key,)
        ).fetchone()

    def idempotent_result(self, key: str) -> Optional[Dict[str, Any]]:
        """Return a defensive copy of a durable command receipt."""
        row = self.find_idempotent(key)
        return self._open_json(
            row["result_json"], table="idempotency", column="result_json", key=key
        ) if row is not None else None

    def claim_command(self, idempotency_key: str, operation_fingerprint: str,
                      command_id: str) -> Dict[str, Any]:
        """Durably admit one long-running command before its external boundary.

        The idempotency table is Core's existing command authority.  Long-running
        commands cannot wait until their final event transaction to claim a key:
        a duplicate arriving during execution must discover the durable admission,
        not race aggregate creation.  A claim is intentionally an in-progress
        receipt, never proof of external completion.
        """
        with self.transaction() as conn:
            prior = conn.execute(
                "SELECT * FROM idempotency WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone()
            if prior is not None:
                if prior["operation_fingerprint"] != operation_fingerprint:
                    raise IdempotencyConflict(
                        "idempotency key %r reused with a different operation fingerprint"
                        % idempotency_key
                    )
                result = self._open_json(
                    prior["result_json"], table="idempotency", column="result_json",
                    key=idempotency_key,
                )
                result["status"] = "idempotent" if result.get("status") != "in_progress" else "in_progress"
                result["replayed"] = True
                return result
            result = {
                "commandId": command_id, "status": "in_progress", "replayed": False,
                "eventIds": [], "globalSequences": [], "streamVersions": [],
            }
            conn.execute(
                "INSERT INTO idempotency (idempotency_key, operation_fingerprint, command_id, result_json, global_sequence) VALUES (?,?,?,?,NULL)",
                (idempotency_key, operation_fingerprint, command_id,
                 self._seal_json(result, table="idempotency", column="result_json", key=idempotency_key)),
            )
            return result

    def complete_claimed_command(self, idempotency_key: str, operation_fingerprint: str,
                                 result: Dict[str, Any]) -> None:
        """Replace an admitted command's provisional receipt with its outcome."""
        with self.transaction() as conn:
            prior = conn.execute(
                "SELECT operation_fingerprint FROM idempotency WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone()
            if prior is None or prior["operation_fingerprint"] != operation_fingerprint:
                raise IdempotencyConflict("cannot complete an unowned command admission")
            conn.execute(
                "UPDATE idempotency SET result_json = ? WHERE idempotency_key = ?",
                (self._seal_json(result, table="idempotency", column="result_json", key=idempotency_key), idempotency_key),
            )

    # -- the single write path --------------------------------------------

    def commit_command(
        self,
        appends: List[AppendRequest],
        idempotency_key: str,
        operation_fingerprint: str,
        command_id: str,
    ) -> Dict[str, Any]:
        """Steps 1-6 of the transaction rule, atomically.

        Aggregate snapshots, durable events, outbox rows, and the idempotency
        record are written in ONE transaction. Nothing is dispatched here:
        publication happens only in dispatch(), strictly after commit
        (spec invariant 10).

        Returns the recorded result. A replayed idempotency key returns the
        ORIGINAL result without writing anything (ADR-0108).
        """
        with self._lock:
            prior = self.find_idempotent(idempotency_key)
            if prior is not None:
                if prior["operation_fingerprint"] != operation_fingerprint:
                    raise IdempotencyConflict(
                        "idempotency key %r reused with a different operation "
                        "fingerprint (stored %s, offered %s)"
                        % (
                            idempotency_key,
                            prior["operation_fingerprint"],
                            operation_fingerprint,
                        )
                    )
                replayed = self._open_json(
                    prior["result_json"], table="idempotency", column="result_json",
                    key=idempotency_key,
                )
                replayed["status"] = "idempotent"
                replayed["replayed"] = True
                return replayed

            with self.transaction() as conn:
                # Re-check inside the write lock: another process may have
                # committed the same key between the read above and BEGIN.
                again = conn.execute(
                    "SELECT * FROM idempotency WHERE idempotency_key = ?",
                    (idempotency_key,),
                ).fetchone()
                if again is not None:
                    if again["operation_fingerprint"] != operation_fingerprint:
                        raise IdempotencyConflict(
                            "idempotency key %r reused with a different operation "
                            "fingerprint" % idempotency_key
                        )
                    replayed = self._open_json(
                        again["result_json"], table="idempotency", column="result_json",
                        key=idempotency_key,
                    )
                    replayed["status"] = "idempotent"
                    replayed["replayed"] = True
                    return replayed

                chain = self.head_chain()
                written: List[Dict[str, Any]] = []

                for append in appends:
                    row = conn.execute(
                        "SELECT version FROM aggregates WHERE stream_id = ?",
                        (append.stream_id,),
                    ).fetchone()
                    actual = int(row["version"]) if row else 0
                    if actual != append.expected_version:
                        raise ConcurrencyConflict(
                            append.stream_id, append.expected_version, actual
                        )

                    next_version = actual + 1
                    envelope = dict(append.envelope)
                    envelope["streamVersion"] = next_version

                    # payloadDigest binds the payload to the envelope. It is
                    # computed here, never accepted from a caller.
                    envelope["payloadDigest"] = digest(envelope["payload"])

                    cursor = conn.execute(
                        "INSERT INTO events (event_id, stream_id, stream_version, "
                        "event_type, schema_version, envelope_json, payload_digest, "
                        "chain_digest) VALUES (?,?,?,?,?,?,?,?)",
                        (
                            envelope["eventId"],
                            append.stream_id,
                            next_version,
                            envelope["eventType"],
                            envelope["schemaVersion"],
                            "",  # rewritten below once globalSequence is known
                            envelope["payloadDigest"],
                            "",
                        ),
                    )
                    global_sequence = int(cursor.lastrowid or 0)
                    envelope["globalSequence"] = global_sequence

                    # Validate the FINAL envelope against the generated
                    # contract before it becomes durable. An invalid event can
                    # never reach the ledger.
                    require("EventEnvelope", envelope)

                    chain = chain_next(chain, envelope["payloadDigest"], envelope["eventId"])
                    conn.execute(
                        "UPDATE events SET envelope_json = ?, chain_digest = ? "
                        "WHERE global_sequence = ?",
                        (self._seal_json(
                            envelope, table="events", column="envelope_json", key=envelope["eventId"]
                         ), chain, global_sequence),
                    )

                    state_json = self._seal_json(
                        append.state, table="aggregates", column="state_json", key=append.stream_id
                    )
                    conn.execute(
                        "INSERT INTO aggregates (stream_id, kind, version, state_json, "
                        "state_digest) VALUES (?,?,?,?,?) "
                        "ON CONFLICT(stream_id) DO UPDATE SET version=excluded.version, "
                        "state_json=excluded.state_json, state_digest=excluded.state_digest",
                        (
                            append.stream_id,
                            append.kind,
                            next_version,
                            state_json,
                            digest(append.state),
                        ),
                    )

                    conn.execute(
                        "INSERT INTO outbox (event_id, global_sequence, status, attempts) "
                        "VALUES (?,?, 'pending', 0)",
                        (envelope["eventId"], global_sequence),
                    )

                    written.append(envelope)

                result = {
                    "commandId": command_id,
                    "status": "applied",
                    "eventIds": [e["eventId"] for e in written],
                    "globalSequences": [e["globalSequence"] for e in written],
                    "streamVersions": [
                        {"streamId": e["streamId"], "version": e["streamVersion"]}
                        for e in written
                    ],
                    "replayed": False,
                }

                conn.execute(
                    "INSERT INTO idempotency (idempotency_key, operation_fingerprint, "
                    "command_id, result_json, global_sequence) VALUES (?,?,?,?,?)",
                    (
                        idempotency_key,
                        operation_fingerprint,
                        command_id,
                        self._seal_json(
                            result, table="idempotency", column="result_json", key=idempotency_key
                        ),
                        written[-1]["globalSequence"] if written else None,
                    ),
                )

            return result

    # -- post-commit dispatch ---------------------------------------------

    def dispatch(self) -> int:
        """Deliver committed events to subscribers, then mark dispatched.

        At-least-once by construction: a crash between handler success and the
        status update replays the handler. Subscribers must be idempotent;
        the conformance suite asserts a replayed dispatch produces no
        duplicate subscriber effect (ADR-0105).
        """
        delivered = 0
        for event_id in self.pending_outbox():
            row = self._conn.execute(
                "SELECT event_id, envelope_json FROM events WHERE event_id = ?", (event_id,)
            ).fetchone()
            if row is None:
                raise IntegrityViolation(
                    "outbox references event %s with no ledger row" % event_id
                )
            envelope = self._open_json(
                row["envelope_json"], table="events", column="envelope_json", key=row["event_id"]
            )
            for handler in self._subscribers:
                handler(envelope)
            with self.transaction() as conn:
                conn.execute(
                    "UPDATE outbox SET status = 'dispatched', attempts = attempts + 1 "
                    "WHERE event_id = ?",
                    (event_id,),
                )
            delivered += 1
        return delivered

    # -- integrity ---------------------------------------------------------

    def verify_chain(self) -> str:
        """Recompute the ledger hash chain. Raises on any mismatch."""
        chain = GENESIS_CHAIN
        rows = self._conn.execute(
            "SELECT event_id, payload_digest, chain_digest, envelope_json, "
            "global_sequence, stream_id, stream_version FROM events "
            "ORDER BY global_sequence ASC"
        ).fetchall()
        last_by_stream: Dict[str, int] = {}
        for row in rows:
            envelope = self._open_json(
                row["envelope_json"], table="events", column="envelope_json", key=row["event_id"]
            )
            recomputed_payload = digest(envelope["payload"])
            if recomputed_payload != row["payload_digest"]:
                raise IntegrityViolation(
                    "payload digest mismatch at event %s" % row["event_id"]
                )
            chain = chain_next(chain, row["payload_digest"], row["event_id"])
            if chain != row["chain_digest"]:
                raise IntegrityViolation(
                    "ledger chain broken at global_sequence %d" % row["global_sequence"]
                )
            previous = last_by_stream.get(row["stream_id"], 0)
            if row["stream_version"] != previous + 1:
                raise IntegrityViolation(
                    "stream %s versions not monotonic: %d follows %d"
                    % (row["stream_id"], row["stream_version"], previous)
                )
            last_by_stream[row["stream_id"]] = row["stream_version"]
        return chain

    def save_checkpoint(self, manifest: Dict[str, Any]) -> None:
        with self.transaction() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO checkpoints (checkpoint_id, manifest_json, "
                "integrity_digest, global_sequence) VALUES (?,?,?,?)",
                (
                    manifest["checkpointId"],
                    self._seal_json(
                        manifest, table="checkpoints", column="manifest_json", key=manifest["checkpointId"]
                    ),
                    manifest["integrityDigest"],
                    manifest["ledgerPosition"]["globalSequence"],
                ),
            )

    def load_checkpoint(self, checkpoint_id: str) -> Dict[str, Any]:
        row = self._conn.execute(
            "SELECT checkpoint_id, manifest_json FROM checkpoints WHERE checkpoint_id = ?",
            (checkpoint_id,),
        ).fetchone()
        if row is None:
            raise NotFound("no checkpoint %s" % checkpoint_id)
        return self._open_json(
            row["manifest_json"], table="checkpoints", column="manifest_json", key=row["checkpoint_id"]
        )

    def latest_checkpoint(self) -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            "SELECT checkpoint_id, manifest_json FROM checkpoints ORDER BY global_sequence DESC, rowid DESC LIMIT 1"
        ).fetchone()
        return self._open_json(
            row["manifest_json"], table="checkpoints", column="manifest_json", key=row["checkpoint_id"]
        ) if row else None

    def record_security_rejection(
        self,
        rejection_id: str,
        rejection_kind: str,
        details: Dict[str, Any],
        source_ip: Optional[str] = None,
        actor_id: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> None:
        """Append one non-secret security rejection to the durable audit trail."""
        ts = timestamp or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO security_rejections "
                "(rejection_id, timestamp, rejection_kind, source_ip, actor_id, details_json) "
                "VALUES (?,?,?,?,?,?)",
                (rejection_id, ts, rejection_kind, source_ip, actor_id,
                 self._seal_json(
                     details, table="security_rejections", column="details_json", key=rejection_id
                 )),
            )

    def list_security_rejections(self, limit: int = 100) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT rejection_id, timestamp, rejection_kind, source_ip, actor_id, details_json "
            "FROM security_rejections ORDER BY timestamp DESC, rowid DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {
                "rejectionId": row["rejection_id"],
                "timestamp": row["timestamp"],
                "rejectionKind": row["rejection_kind"],
                "sourceIp": row["source_ip"],
                "actorId": row["actor_id"],
                "details": self._open_json(
                    row["details_json"], table="security_rejections", column="details_json",
                    key=row["rejection_id"],
                ),
            }
            for row in rows
        ]
