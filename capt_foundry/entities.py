"""Research Entity Registry and Research Alias Registry (ADR-0130).

An Entity is a real-world research subject — person, organization, place, work,
event — with an identity that outlives any single claim, memory row, or case.
An Alias is a name that resolves to one entity.

Alias resolution NEVER guesses. When a name maps to more than one active entity
the registry raises ``AmbiguousAlias`` carrying every candidate, so a human
disambiguates. Silently picking the "best" match is how research corpora acquire
false joins, and the Foundry exists to prevent exactly that.

Neither registry stores evidence bodies or verification verdicts. ``evidence_ids``
are references into runtime-owned evidence (ADR-0130).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from capt_foundry.canonical import (
    digest,
    is_identifier,
    normalize_name,
    utc_now,
)
from capt_foundry.errors import (
    AmbiguousAlias,
    DuplicateIdentity,
    UnknownEntity,
    ValidationError,
)
from capt_foundry.storage import FoundryStore

ENTITY_TYPES = ("person", "organization", "place", "work", "event", "concept", "other")
ALIAS_KINDS = (
    "also_known_as",
    "former_name",
    "abbreviation",
    "translation",
    "misspelling",
)
ALIAS_CONFIDENCE = ("asserted", "evidence_backed", "human_confirmed")


@dataclass(frozen=True)
class Entity:
    """A research subject. Immutable; a change produces a new record."""

    entity_id: str
    entity_type: str
    canonical_name: str
    description: str = ""
    evidence_ids: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    status: str = "active"
    superseded_by: str | None = None

    def __post_init__(self) -> None:
        problems: list[str] = []
        if not is_identifier(self.entity_id):
            problems.append("entity_id must match Identifier pattern")
        if self.entity_type not in ENTITY_TYPES:
            problems.append(f"entity_type must be one of {ENTITY_TYPES}")
        if not self.canonical_name.strip():
            problems.append("canonical_name required")
        if self.status not in ("active", "superseded"):
            problems.append("status must be active|superseded")
        if self.superseded_by is not None and self.status != "superseded":
            problems.append("superseded_by set but status is not 'superseded'")
        if not isinstance(self.evidence_ids, list):
            problems.append("evidence_ids must be a list")
        if problems:
            raise ValidationError("Entity", problems)

    @property
    def normalized_name(self) -> str:
        return normalize_name(self.canonical_name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "canonical_name": self.canonical_name,
            "normalized_name": self.normalized_name,
            "description": self.description,
            "evidence_ids": list(self.evidence_ids),
            "attributes": dict(self.attributes),
            "status": self.status,
            "superseded_by": self.superseded_by,
        }

    def digest(self) -> str:
        return digest(self.to_dict())


@dataclass(frozen=True)
class EntityAlias:
    """A name that resolves to an entity."""

    alias_id: str
    entity_id: str
    alias: str
    alias_kind: str = "also_known_as"
    confidence: str = "asserted"
    evidence_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        problems: list[str] = []
        if not is_identifier(self.alias_id):
            problems.append("alias_id must match Identifier pattern")
        if not is_identifier(self.entity_id):
            problems.append("entity_id must match Identifier pattern")
        if not self.alias.strip():
            problems.append("alias required")
        if self.alias_kind not in ALIAS_KINDS:
            problems.append(f"alias_kind must be one of {ALIAS_KINDS}")
        if self.confidence not in ALIAS_CONFIDENCE:
            problems.append(f"confidence must be one of {ALIAS_CONFIDENCE}")
        if self.confidence == "evidence_backed" and not self.evidence_ids:
            problems.append("confidence 'evidence_backed' requires evidence_ids")
        if problems:
            raise ValidationError("EntityAlias", problems)

    @property
    def normalized_alias(self) -> str:
        return normalize_name(self.alias)

    def to_dict(self) -> dict[str, Any]:
        return {
            "alias_id": self.alias_id,
            "entity_id": self.entity_id,
            "alias": self.alias,
            "normalized_alias": self.normalized_alias,
            "alias_kind": self.alias_kind,
            "confidence": self.confidence,
            "evidence_ids": list(self.evidence_ids),
        }

    def digest(self) -> str:
        return digest(self.to_dict())


class EntityRegistry:
    """Durable identity for research subjects."""

    def __init__(self, store: FoundryStore, clock=utc_now) -> None:
        self.store = store
        self._clock = clock

    def register(self, entity: Entity, actor: str) -> str:
        if not actor.strip():
            raise ValidationError("register", ["actor required"])
        existing = self.get(entity.entity_id)
        if existing is not None:
            # Idempotent: identical content is a no-op, not a duplicate.
            if existing["record_digest"] == entity.digest():
                return entity.entity_id
            raise DuplicateIdentity(
                f"entity {entity.entity_id} already registered with different content"
            )
        now = self._clock()
        d = entity.to_dict()
        self.store.conn.execute(
            """INSERT INTO entities (entity_id, entity_type, canonical_name,
                   normalized_name, description, evidence_ids, attributes, status,
                   superseded_by, record_digest, registered_by, registered_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                d["entity_id"],
                d["entity_type"],
                d["canonical_name"],
                d["normalized_name"],
                d["description"],
                json.dumps(d["evidence_ids"]),
                json.dumps(d["attributes"], sort_keys=True),
                d["status"],
                d["superseded_by"],
                entity.digest(),
                actor,
                now,
            ),
        )
        self.store.conn.commit()
        return entity.entity_id

    def get(self, entity_id: str) -> dict[str, Any] | None:
        row = self.store.conn.execute(
            "SELECT * FROM entities WHERE entity_id = ?", (entity_id,)
        ).fetchone()
        return self._row(row) if row is not None else None

    def require(self, entity_id: str) -> dict[str, Any]:
        found = self.get(entity_id)
        if found is None:
            raise UnknownEntity(f"entity {entity_id} is not registered")
        return found

    def all(self) -> list[dict[str, Any]]:
        rows = self.store.conn.execute(
            "SELECT * FROM entities ORDER BY entity_id"
        ).fetchall()
        return [self._row(r) for r in rows]

    def find_by_name(self, name: str) -> list[dict[str, Any]]:
        """Exact match on the normalized canonical name. Active entities only."""
        rows = self.store.conn.execute(
            "SELECT * FROM entities WHERE normalized_name = ? AND status = 'active'"
            " ORDER BY entity_id",
            (normalize_name(name),),
        ).fetchall()
        return [self._row(r) for r in rows]

    def merge(self, source_id: str, target_id: str, actor: str) -> None:
        """Mark ``source`` superseded by ``target``. Recoverable, never deleting.

        The source row is retained so historical references still resolve, and
        its aliases are re-pointed at the target so a future lookup of the old
        name finds the surviving entity.
        """
        if source_id == target_id:
            raise ValidationError("merge", ["cannot merge an entity into itself"])
        self.require(source_id)
        self.require(target_id)
        conn = self.store.conn
        conn.execute(
            "UPDATE entities SET status='superseded', superseded_by=? WHERE entity_id=?",
            (target_id, source_id),
        )
        # Re-point aliases, skipping any the target already carries.
        for row in conn.execute(
            "SELECT alias_id, normalized_alias FROM entity_aliases WHERE entity_id=?",
            (source_id,),
        ).fetchall():
            clash = conn.execute(
                "SELECT 1 FROM entity_aliases WHERE entity_id=? AND normalized_alias=?",
                (target_id, row["normalized_alias"]),
            ).fetchone()
            if clash is None:
                conn.execute(
                    "UPDATE entity_aliases SET entity_id=? WHERE alias_id=?",
                    (target_id, row["alias_id"]),
                )
        conn.commit()

    @staticmethod
    def _row(row) -> dict[str, Any]:
        d = dict(row)
        d["evidence_ids"] = json.loads(d["evidence_ids"])
        d["attributes"] = json.loads(d["attributes"])
        return d


class AliasRegistry:
    """Name resolution for research subjects. Refuses to guess."""

    def __init__(self, store: FoundryStore, entities: EntityRegistry, clock=utc_now) -> None:
        self.store = store
        self.entities = entities
        self._clock = clock

    def register(self, alias: EntityAlias, actor: str) -> str:
        if not actor.strip():
            raise ValidationError("register", ["actor required"])
        self.entities.require(alias.entity_id)  # no dangling aliases
        existing = self.store.conn.execute(
            "SELECT * FROM entity_aliases WHERE alias_id = ?", (alias.alias_id,)
        ).fetchone()
        if existing is not None:
            if existing["record_digest"] == alias.digest():
                return alias.alias_id
            raise DuplicateIdentity(
                f"alias {alias.alias_id} already registered with different content"
            )
        clash = self.store.conn.execute(
            "SELECT alias_id FROM entity_aliases WHERE entity_id=? AND normalized_alias=?",
            (alias.entity_id, alias.normalized_alias),
        ).fetchone()
        if clash is not None:
            raise DuplicateIdentity(
                "entity {} already has alias {!r} (as {})".format(alias.entity_id, alias.alias, clash["alias_id"])
            )
        d = alias.to_dict()
        self.store.conn.execute(
            """INSERT INTO entity_aliases (alias_id, entity_id, alias,
                   normalized_alias, alias_kind, confidence, evidence_ids,
                   record_digest, registered_by, registered_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                d["alias_id"],
                d["entity_id"],
                d["alias"],
                d["normalized_alias"],
                d["alias_kind"],
                d["confidence"],
                json.dumps(d["evidence_ids"]),
                alias.digest(),
                actor,
                self._clock(),
            ),
        )
        self.store.conn.commit()
        return alias.alias_id

    def resolve(self, name: str) -> dict[str, Any]:
        """Resolve a name to exactly one active entity.

        Raises ``UnknownEntity`` if nothing matches and ``AmbiguousAlias`` if more
        than one active entity matches. Never returns a best guess.
        """
        candidates = self.candidates(name)
        if not candidates:
            raise UnknownEntity(f"no entity resolves from name {name!r}")
        if len(candidates) > 1:
            raise AmbiguousAlias(name, [c["entity_id"] for c in candidates])
        return candidates[0]

    def candidates(self, name: str) -> list[dict[str, Any]]:
        """Every ACTIVE entity reachable from ``name`` by alias or canonical name.

        A superseded entity resolves through to its surviving target, so an old
        name keeps working after a merge.
        """
        norm = normalize_name(name)
        conn = self.store.conn
        ids: list[str] = []
        for row in conn.execute(
            "SELECT entity_id FROM entity_aliases WHERE normalized_alias = ?", (norm,)
        ).fetchall():
            ids.append(row["entity_id"])
        for row in conn.execute(
            "SELECT entity_id FROM entities WHERE normalized_name = ?", (norm,)
        ).fetchall():
            ids.append(row["entity_id"])

        resolved: dict[str, dict[str, Any]] = {}
        for eid in ids:
            ent = self.entities.get(eid)
            seen = set()
            while ent is not None and ent["status"] == "superseded":
                if ent["entity_id"] in seen:  # cycle guard
                    break
                seen.add(ent["entity_id"])
                nxt = ent.get("superseded_by")
                if not nxt:
                    break
                ent = self.entities.get(nxt)
            if ent is not None and ent["status"] == "active":
                resolved[ent["entity_id"]] = ent
        return [resolved[k] for k in sorted(resolved)]

    def aliases_for(self, entity_id: str) -> list[dict[str, Any]]:
        rows = self.store.conn.execute(
            "SELECT * FROM entity_aliases WHERE entity_id = ? ORDER BY alias_id",
            (entity_id,),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["evidence_ids"] = json.loads(d["evidence_ids"])
            out.append(d)
        return out
