"""Corpus and Document Manifest (ADR-0130).

Inventories a set of documents with per-document content digest, byte size, and
locator, plus a manifest-level digest over the whole membership. This is what
lets a consumer ask "have we already ingested this corpus, and is it still the
one we hashed?" without re-scanning.

METADATA ONLY. Document bodies are never stored or copied. Indexing reads bytes
solely to compute a digest, and only inside a caller-declared root: path
traversal and symlink escape fail closed. There is no recursive auto-discovery
beyond the declared root, and no network access.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

from capt_foundry.canonical import (
    digest,
    is_digest,
    is_identifier,
    utc_now,
)
from capt_foundry.errors import (
    DuplicateIdentity,
    PathEscape,
    UnknownEntity,
    ValidationError,
)
from capt_foundry.storage import FoundryStore

_READ_CHUNK = 1024 * 1024


def _safe_resolve(root: Path, relative: str) -> Path:
    """Resolve ``relative`` under ``root``, refusing every escape route."""
    if Path(relative).is_absolute():
        raise PathEscape("absolute path not permitted: %r" % relative)
    root_resolved = root.resolve()
    target = (root_resolved / relative).resolve()
    try:
        target.relative_to(root_resolved)
    except ValueError:
        raise PathEscape("%r escapes corpus root %s" % (relative, root_resolved))
    # Reject a symlink anywhere between root and target, even if the resolved
    # destination happens to land back inside the root.
    cur = root_resolved / relative
    while cur != root_resolved and cur.parent != cur:
        if cur.is_symlink():
            raise PathEscape("symlink in path at %s" % cur)
        cur = cur.parent
    return target


@dataclass(frozen=True)
class Document:
    """Metadata for one document. Never the body."""

    document_id: str
    relative_path: str
    content_digest: str
    byte_size: int
    media_type: str = "application/octet-stream"
    locator: str = ""

    def __post_init__(self) -> None:
        problems: List[str] = []
        if not is_identifier(self.document_id):
            problems.append("document_id must match Identifier pattern")
        if not self.relative_path.strip():
            problems.append("relative_path required")
        if not is_digest(self.content_digest):
            problems.append("content_digest must be sha256:<64 hex>")
        if self.byte_size < 0:
            problems.append("byte_size must be >= 0")
        if problems:
            raise ValidationError("Document", problems)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "relative_path": self.relative_path,
            "content_digest": self.content_digest,
            "byte_size": self.byte_size,
            "media_type": self.media_type,
            "locator": self.locator,
        }

    def digest(self) -> str:
        return digest(self.to_dict())


@dataclass(frozen=True)
class CorpusManifest:
    """A named, digest-stable set of documents."""

    corpus_id: str
    name: str
    root_label: str
    description: str = ""
    documents: List[Document] = field(default_factory=list)

    def __post_init__(self) -> None:
        problems: List[str] = []
        if not is_identifier(self.corpus_id):
            problems.append("corpus_id must match Identifier pattern")
        if not self.name.strip():
            problems.append("name required")
        if not self.root_label.strip():
            problems.append("root_label required (a label, not a filesystem path)")
        seen_ids, seen_paths = set(), set()
        for doc in self.documents:
            if doc.document_id in seen_ids:
                problems.append("duplicate document_id %s" % doc.document_id)
            if doc.relative_path in seen_paths:
                problems.append("duplicate relative_path %s" % doc.relative_path)
            seen_ids.add(doc.document_id)
            seen_paths.add(doc.relative_path)
        if problems:
            raise ValidationError("CorpusManifest", problems)

    def manifest_digest(self) -> str:
        """Digest over identity plus sorted membership.

        Sorted by document_id so insertion order cannot change the digest, and
        membership-sensitive so adding or removing a document changes it.
        """
        return digest(
            {
                "corpus_id": self.corpus_id,
                "name": self.name,
                "root_label": self.root_label,
                "description": self.description,
                "documents": [
                    d.to_dict() for d in sorted(self.documents, key=lambda x: x.document_id)
                ],
            }
        )

    def duplicate_groups(self) -> Dict[str, List[str]]:
        """content_digest -> document_ids, for digests appearing more than once."""
        by_digest: Dict[str, List[str]] = {}
        for doc in self.documents:
            by_digest.setdefault(doc.content_digest, []).append(doc.document_id)
        return {k: sorted(v) for k, v in by_digest.items() if len(v) > 1}


class CorpusRegistry(object):
    """Registers corpora and their document metadata."""

    def __init__(self, store: FoundryStore, clock=utc_now) -> None:
        self.store = store
        self._clock = clock

    def register(self, manifest: CorpusManifest, actor: str) -> str:
        if not actor.strip():
            raise ValidationError("register", ["actor required"])
        conn = self.store.conn
        existing = conn.execute(
            "SELECT manifest_digest FROM corpora WHERE corpus_id = ?",
            (manifest.corpus_id,),
        ).fetchone()
        md = manifest.manifest_digest()
        if existing is not None:
            if existing["manifest_digest"] == md:
                return manifest.corpus_id  # idempotent
            raise DuplicateIdentity(
                "corpus %s already registered with a different manifest digest"
                % manifest.corpus_id
            )
        now = self._clock()
        conn.execute(
            """INSERT INTO corpora (corpus_id, name, root_label, description,
                   manifest_digest, document_count, status, last_validated_at,
                   registered_by, registered_at)
               VALUES (?,?,?,?,?,?,'current',?,?,?)""",
            (
                manifest.corpus_id,
                manifest.name,
                manifest.root_label,
                manifest.description,
                md,
                len(manifest.documents),
                now,
                actor,
                now,
            ),
        )
        for doc in manifest.documents:
            d = doc.to_dict()
            conn.execute(
                """INSERT INTO documents (document_id, corpus_id, relative_path,
                       content_digest, byte_size, media_type, locator,
                       record_digest, indexed_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    d["document_id"],
                    manifest.corpus_id,
                    d["relative_path"],
                    d["content_digest"],
                    d["byte_size"],
                    d["media_type"],
                    d["locator"],
                    doc.digest(),
                    now,
                ),
            )
        conn.commit()
        return manifest.corpus_id

    def get(self, corpus_id: str) -> Optional[Dict[str, Any]]:
        row = self.store.conn.execute(
            "SELECT * FROM corpora WHERE corpus_id = ?", (corpus_id,)
        ).fetchone()
        return dict(row) if row is not None else None

    def require(self, corpus_id: str) -> Dict[str, Any]:
        found = self.get(corpus_id)
        if found is None:
            raise UnknownEntity("corpus %s is not registered" % corpus_id)
        return found

    def documents(self, corpus_id: str) -> List[Dict[str, Any]]:
        rows = self.store.conn.execute(
            "SELECT * FROM documents WHERE corpus_id = ? ORDER BY document_id",
            (corpus_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def find_by_content_digest(self, content_digest: str) -> List[Dict[str, Any]]:
        """Cross-corpus duplicate detection: never re-ingest the same bytes."""
        rows = self.store.conn.execute(
            "SELECT * FROM documents WHERE content_digest = ?"
            " ORDER BY corpus_id, document_id",
            (content_digest,),
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_stale(self, corpus_id: str) -> None:
        """Freshness: a corpus whose source may have changed is not silently trusted."""
        self.require(corpus_id)
        self.store.conn.execute(
            "UPDATE corpora SET status = 'stale' WHERE corpus_id = ?", (corpus_id,)
        )
        self.store.conn.commit()

    def mark_current(self, corpus_id: str) -> None:
        self.require(corpus_id)
        self.store.conn.execute(
            "UPDATE corpora SET status='current', last_validated_at=? WHERE corpus_id=?",
            (self._clock(), corpus_id),
        )
        self.store.conn.commit()

    def verify_against_manifest(self, manifest: CorpusManifest) -> Dict[str, Any]:
        """Compare a freshly built manifest with what is stored.

        Returns a difference report. Does not mutate; the caller decides.
        """
        stored = self.require(manifest.corpus_id)
        stored_docs = {d["document_id"]: d for d in self.documents(manifest.corpus_id)}
        new_docs = {d.document_id: d for d in manifest.documents}
        changed = [
            did
            for did in sorted(set(stored_docs) & set(new_docs))
            if stored_docs[did]["content_digest"] != new_docs[did].content_digest
        ]
        return {
            "corpus_id": manifest.corpus_id,
            "matches": stored["manifest_digest"] == manifest.manifest_digest(),
            "stored_digest": stored["manifest_digest"],
            "computed_digest": manifest.manifest_digest(),
            "added": sorted(set(new_docs) - set(stored_docs)),
            "removed": sorted(set(stored_docs) - set(new_docs)),
            "changed": changed,
        }


def index_directory(
    corpus_id: str,
    name: str,
    root: Union[str, Path],
    *,
    relative_paths: Iterable[str],
    root_label: Optional[str] = None,
    description: str = "",
    media_type: str = "application/octet-stream",
) -> CorpusManifest:
    """Build a manifest from an EXPLICIT list of paths under ``root``.

    Deliberately NOT a recursive scan. The Captain's constraints forbid broad
    scans and uncontrolled ingestion, so the caller names every document. Each
    path is confined to ``root``; traversal and symlinks fail closed. Bytes are
    read only to digest them and are never retained.
    """
    root_path = Path(root)
    if not root_path.is_dir():
        raise ValidationError("index_directory", ["root %s is not a directory" % root])
    docs: List[Document] = []
    for idx, rel in enumerate(sorted(set(relative_paths))):
        target = _safe_resolve(root_path, rel)
        if not target.is_file():
            raise ValidationError("index_directory", ["not a regular file: %s" % rel])
        h_total = 0
        sha = hashlib.sha256()
        with open(target, "rb") as fh:
            while True:
                chunk = fh.read(_READ_CHUNK)
                if not chunk:
                    break
                h_total += len(chunk)
                sha.update(chunk)
        docs.append(
            Document(
                document_id="%s.d%04d" % (corpus_id, idx),
                relative_path=rel,
                content_digest="sha256:" + sha.hexdigest(),
                byte_size=h_total,
                media_type=media_type,
                locator=rel,
            )
        )
    return CorpusManifest(
        corpus_id=corpus_id,
        name=name,
        root_label=root_label or root_path.name,
        description=description,
        documents=docs,
    )
