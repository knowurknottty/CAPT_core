"""Foundry SQLite storage.

A SEPARATE database file from ``runtime.db`` and ``memory.db``, for the reason
ADR-0104 gives for separating the runtime store from memory: different authority
owner, different lifecycle, different backup policy. Sharing a file would let
Foundry curation mutate runtime state through a shared connection.

This module owns schema creation and versioning only. It performs no domain
logic and appends no runtime events — the Foundry writes no event ledger
(ADR-0130).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from typing_extensions import Self

from capt_foundry.canonical import FOUNDRY_SCHEMA_VERSION
from capt_foundry.errors import PathEscape, ValidationError

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS foundry_schema_version (
    version TEXT NOT NULL,
    single  INTEGER PRIMARY KEY CHECK (single = 1)
);

CREATE TABLE IF NOT EXISTS entities (
    entity_id     TEXT PRIMARY KEY,
    entity_type   TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    evidence_ids  TEXT NOT NULL DEFAULT '[]',
    attributes    TEXT NOT NULL DEFAULT '{}',
    status        TEXT NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active','superseded')),
    superseded_by TEXT,
    record_digest TEXT NOT NULL,
    registered_by TEXT NOT NULL,
    registered_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entity_aliases (
    alias_id      TEXT PRIMARY KEY,
    entity_id     TEXT NOT NULL REFERENCES entities(entity_id),
    alias         TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,
    alias_kind    TEXT NOT NULL DEFAULT 'also_known_as',
    confidence    TEXT NOT NULL DEFAULT 'asserted'
                  CHECK (confidence IN ('asserted','evidence_backed','human_confirmed')),
    evidence_ids  TEXT NOT NULL DEFAULT '[]',
    record_digest TEXT NOT NULL,
    registered_by TEXT NOT NULL,
    registered_at TEXT NOT NULL,
    UNIQUE (entity_id, normalized_alias)
);

CREATE TABLE IF NOT EXISTS corpora (
    corpus_id     TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    root_label    TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    manifest_digest TEXT NOT NULL,
    document_count INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'current'
                  CHECK (status IN ('current','stale')),
    last_validated_at TEXT,
    registered_by TEXT NOT NULL,
    registered_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    document_id   TEXT PRIMARY KEY,
    corpus_id     TEXT NOT NULL REFERENCES corpora(corpus_id),
    relative_path TEXT NOT NULL,
    content_digest TEXT NOT NULL,
    byte_size     INTEGER NOT NULL CHECK (byte_size >= 0),
    media_type    TEXT NOT NULL DEFAULT 'application/octet-stream',
    locator       TEXT NOT NULL DEFAULT '',
    record_digest TEXT NOT NULL,
    indexed_at    TEXT NOT NULL,
    UNIQUE (corpus_id, relative_path)
);

CREATE TABLE IF NOT EXISTS assets (
    asset_id      TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    asset_version TEXT NOT NULL,
    entity_ids    TEXT NOT NULL DEFAULT '[]',
    corpus_ids    TEXT NOT NULL DEFAULT '[]',
    evidence_ids  TEXT NOT NULL DEFAULT '[]',
    manifest_json TEXT NOT NULL,
    manifest_hash TEXT NOT NULL,
    published_by  TEXT NOT NULL,
    published_at  TEXT NOT NULL,
    UNIQUE (name, asset_version)
);

CREATE INDEX IF NOT EXISTS idx_alias_lookup ON entity_aliases (normalized_alias);
CREATE INDEX IF NOT EXISTS idx_entity_norm ON entities (normalized_name);
CREATE INDEX IF NOT EXISTS idx_doc_digest ON documents (content_digest);
CREATE INDEX IF NOT EXISTS idx_doc_corpus ON documents (corpus_id);
"""


def _check_path(db_path: Path, root: Path) -> None:
    """Confine the database to a declared root; refuse traversal and symlinks."""
    try:
        db_path.resolve().relative_to(root.resolve())
    except ValueError:
        raise PathEscape(f"database path {db_path} escapes root {root}")
    cur = db_path
    root_resolved = root.resolve()
    while True:
        if cur.is_symlink():
            raise PathEscape(f"symlink in database path at {cur}")
        if cur.resolve() == root_resolved or cur.parent == cur:
            break
        cur = cur.parent


class FoundryStore:
    """Owns the Foundry SQLite connection and schema.

    Pass ``":memory:"`` for an ephemeral store (tests). A filesystem path is
    confined to ``allowed_root``, defaulting to the path's own parent.
    """

    def __init__(
        self,
        db_path: str | Path = ":memory:",
        allowed_root: str | Path | None = None,
    ) -> None:
        if str(db_path) == ":memory:":
            self.db_path = ":memory:"
            self.allowed_root = None
        else:
            path = Path(db_path)
            root = Path(allowed_root) if allowed_root is not None else path.parent
            _check_path(path, root)
            path.parent.mkdir(parents=True, exist_ok=True)
            self.db_path = str(path)
            self.allowed_root = root
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_SQL)
        self._init_version()

    def _init_version(self) -> None:
        row = self.conn.execute(
            "SELECT version FROM foundry_schema_version WHERE single = 1"
        ).fetchone()
        if row is None:
            self.conn.execute(
                "INSERT INTO foundry_schema_version (version, single) VALUES (?, 1)",
                (FOUNDRY_SCHEMA_VERSION,),
            )
            self.conn.commit()
        elif row["version"] != FOUNDRY_SCHEMA_VERSION:
            raise ValidationError(
                "foundry_schema_version",
                [
                    "store was created by schema {!r}, this code speaks {!r}; a "
                    "migration is required".format(row["version"], FOUNDRY_SCHEMA_VERSION)
                ],
            )

    @property
    def schema_version(self) -> str:
        row = self.conn.execute(
            "SELECT version FROM foundry_schema_version WHERE single = 1"
        ).fetchone()
        return str(row["version"])

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
