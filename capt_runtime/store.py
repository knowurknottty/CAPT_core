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
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from .contracts import canonical_json, digest, require
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

CREATE INDEX IF NOT EXISTS idx_events_stream ON events (stream_id, stream_version);
CREATE INDEX IF NOT EXISTS idx_outbox_pending ON outbox (status, global_sequence);
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
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA_SQL)
        self._subscribers: List[Callable[[Dict[str, Any]], None]] = []

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
            "SELECT state_json FROM aggregates WHERE stream_id = ?", (stream_id,)
        ).fetchone()
        return json.loads(row["state_json"]) if row else None

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
            "SELECT envelope_json FROM events WHERE global_sequence > ? "
            "ORDER BY global_sequence ASC",
            (after_sequence,),
        ).fetchall()
        return [json.loads(r["envelope_json"]) for r in rows]

    def read_stream(self, stream_id: str) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT envelope_json FROM events WHERE stream_id = ? "
            "ORDER BY stream_version ASC",
            (stream_id,),
        ).fetchall()
        return [json.loads(r["envelope_json"]) for r in rows]

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
                result = json.loads(prior["result_json"])
                result["status"] = "idempotent" if result.get("status") != "in_progress" else "in_progress"
                result["replayed"] = True
                return result
            result = {
                "commandId": command_id, "status": "in_progress", "replayed": False,
                "eventIds": [], "globalSequences": [], "streamVersions": [],
            }
            conn.execute(
                "INSERT INTO idempotency (idempotency_key, operation_fingerprint, command_id, result_json, global_sequence) VALUES (?,?,?,?,NULL)",
                (idempotency_key, operation_fingerprint, command_id, canonical_json(result)),
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
                (canonical_json(result), idempotency_key),
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
                replayed = json.loads(prior["result_json"])
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
                    replayed = json.loads(again["result_json"])
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
                        (canonical_json(envelope), chain, global_sequence),
                    )

                    state_json = canonical_json(append.state)
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
                        canonical_json(result),
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
                "SELECT envelope_json FROM events WHERE event_id = ?", (event_id,)
            ).fetchone()
            if row is None:
                raise IntegrityViolation(
                    "outbox references event %s with no ledger row" % event_id
                )
            envelope = json.loads(row["envelope_json"])
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
            envelope = json.loads(row["envelope_json"])
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
                    canonical_json(manifest),
                    manifest["integrityDigest"],
                    manifest["ledgerPosition"]["globalSequence"],
                ),
            )

    def load_checkpoint(self, checkpoint_id: str) -> Dict[str, Any]:
        row = self._conn.execute(
            "SELECT manifest_json FROM checkpoints WHERE checkpoint_id = ?",
            (checkpoint_id,),
        ).fetchone()
        if row is None:
            raise NotFound("no checkpoint %s" % checkpoint_id)
        return json.loads(row["manifest_json"])

    def latest_checkpoint(self) -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            "SELECT manifest_json FROM checkpoints ORDER BY global_sequence DESC, rowid DESC LIMIT 1"
        ).fetchone()
        return json.loads(row["manifest_json"]) if row else None
