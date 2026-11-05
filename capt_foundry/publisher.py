"""Curated Artifact Publisher (ADR-0130).

Assembles Foundry registry contents into a reusable, hash-verifiable asset and
records the publication. It REUSES the existing Knowledge Bubble format
(``capt_solo/foundry/bubble.py``) and defines no second format.

``KnowledgeBubbleRuntime.build_bubble`` is a ``@staticmethod``, so the publisher
calls it directly WITHOUT instantiating the runtime. That matters: instantiating
a canonical subsystem here would create a parallel construction path and violate
the composition-root invariant. The publisher owns curation; the bubble module
owns the format.

Publication refuses dangling references. An asset that cites an unregistered
entity or corpus is a broken asset, and it is cheaper to reject it than to let a
consumer discover the break later.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from capt_foundry.canonical import digest, is_identifier, utc_now
from capt_foundry.corpus import CorpusRegistry
from capt_foundry.entities import AliasRegistry, EntityRegistry
from capt_foundry.errors import DanglingReference, DuplicateIdentity, ValidationError
from capt_foundry.storage import FoundryStore

ASSET_FORMAT = "capt.foundry.research_asset"
ASSET_FORMAT_VERSION = "1.0.0"


@dataclass(frozen=True)
class CuratedAsset:
    """A named, versioned bundle of research assets."""

    asset_id: str
    name: str
    asset_version: str = "1.0.0"
    entity_ids: list[str] = field(default_factory=list)
    corpus_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    summary: str = ""

    def __post_init__(self) -> None:
        problems: list[str] = []
        if not is_identifier(self.asset_id):
            problems.append("asset_id must match Identifier pattern")
        if not self.name.strip():
            problems.append("name required")
        if not self.asset_version.strip():
            problems.append("asset_version required")
        if not self.entity_ids and not self.corpus_ids:
            problems.append("asset must reference at least one entity or corpus")
        if problems:
            raise ValidationError("CuratedAsset", problems)


class ArtifactPublisher:
    """Turns registry contents into a portable, verifiable asset."""

    def __init__(
        self,
        store: FoundryStore,
        entities: EntityRegistry,
        aliases: AliasRegistry,
        corpora: CorpusRegistry,
        clock=utc_now,
    ) -> None:
        self.store = store
        self.entities = entities
        self.aliases = aliases
        self.corpora = corpora
        self._clock = clock

    # -- payload -----------------------------------------------------------

    def build_payload(self, asset: CuratedAsset) -> dict[str, Any]:
        """Resolve references into a deterministic, provenance-preserving payload."""
        entity_records: list[dict[str, Any]] = []
        for eid in sorted(set(asset.entity_ids)):
            row = self.entities.get(eid)
            if row is None:
                raise DanglingReference(f"asset cites unregistered entity {eid}")
            entity_records.append(
                {
                    "entity_id": row["entity_id"],
                    "entity_type": row["entity_type"],
                    "canonical_name": row["canonical_name"],
                    "normalized_name": row["normalized_name"],
                    "description": row["description"],
                    "status": row["status"],
                    "superseded_by": row["superseded_by"],
                    "evidence_ids": row["evidence_ids"],
                    "attributes": row["attributes"],
                    "record_digest": row["record_digest"],
                    "provenance": {
                        "registered_by": row["registered_by"],
                        "registered_at": row["registered_at"],
                    },
                    "aliases": [
                        {
                            "alias_id": a["alias_id"],
                            "alias": a["alias"],
                            "normalized_alias": a["normalized_alias"],
                            "alias_kind": a["alias_kind"],
                            "confidence": a["confidence"],
                            "evidence_ids": a["evidence_ids"],
                            "record_digest": a["record_digest"],
                            "provenance": {
                                "registered_by": a["registered_by"],
                                "registered_at": a["registered_at"],
                            },
                        }
                        for a in self.aliases.aliases_for(eid)
                    ],
                }
            )

        corpus_records: list[dict[str, Any]] = []
        for cid in sorted(set(asset.corpus_ids)):
            row = self.corpora.get(cid)
            if row is None:
                raise DanglingReference(f"asset cites unregistered corpus {cid}")
            corpus_records.append(
                {
                    "corpus_id": row["corpus_id"],
                    "name": row["name"],
                    "root_label": row["root_label"],
                    "description": row["description"],
                    "manifest_digest": row["manifest_digest"],
                    "document_count": row["document_count"],
                    "status": row["status"],
                    "last_validated_at": row["last_validated_at"],
                    "provenance": {
                        "registered_by": row["registered_by"],
                        "registered_at": row["registered_at"],
                    },
                    "documents": [
                        {
                            "document_id": d["document_id"],
                            "relative_path": d["relative_path"],
                            "content_digest": d["content_digest"],
                            "byte_size": d["byte_size"],
                            "media_type": d["media_type"],
                            "locator": d["locator"],
                            "record_digest": d["record_digest"],
                            "indexed_at": d["indexed_at"],
                        }
                        for d in self.corpora.documents(cid)
                    ],
                }
            )

        return {
            "format": ASSET_FORMAT,
            "format_version": ASSET_FORMAT_VERSION,
            "asset_id": asset.asset_id,
            "name": asset.name,
            "asset_version": asset.asset_version,
            "summary": asset.summary,
            "entities": entity_records,
            "corpora": corpus_records,
            # References into runtime-owned evidence. NEVER evidence bodies or
            # verification verdicts — the Foundry does not own evidence.
            "evidence_refs": sorted(set(asset.evidence_ids)),
        }

    # -- publication -------------------------------------------------------

    def publish(
        self,
        asset: CuratedAsset,
        actor: str,
        *,
        published_at: str | None = None,
    ) -> dict[str, Any]:
        """Build the payload, wrap it in a Knowledge Bubble manifest, record it.

        Deterministic: identical registry content and identical ``published_at``
        yield a byte-identical manifest apart from fields the bubble format
        stamps itself.
        """
        if not actor.strip():
            raise ValidationError("publish", ["actor required"])
        payload = self.build_payload(asset)
        stamp = published_at or self._clock()
        payload_digest = digest(payload)

        manifest = self._build_manifest(asset, payload, payload_digest, actor, stamp)
        manifest_hash = manifest.get("manifest_hash") or digest(manifest)

        conn = self.store.conn
        existing = conn.execute(
            "SELECT manifest_hash FROM assets WHERE asset_id = ?", (asset.asset_id,)
        ).fetchone()
        if existing is not None:
            if existing["manifest_hash"] == manifest_hash:
                return json.loads(
                    conn.execute(
                        "SELECT manifest_json FROM assets WHERE asset_id = ?",
                        (asset.asset_id,),
                    ).fetchone()["manifest_json"]
                )
            raise DuplicateIdentity(
                f"asset {asset.asset_id} already published with a different manifest hash"
            )

        conn.execute(
            """INSERT INTO assets (asset_id, name, asset_version, entity_ids,
                   corpus_ids, evidence_ids, manifest_json, manifest_hash,
                   published_by, published_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                asset.asset_id,
                asset.name,
                asset.asset_version,
                json.dumps(sorted(set(asset.entity_ids))),
                json.dumps(sorted(set(asset.corpus_ids))),
                json.dumps(sorted(set(asset.evidence_ids))),
                json.dumps(manifest, sort_keys=True),
                manifest_hash,
                actor,
                stamp,
            ),
        )
        conn.commit()
        return manifest

    def _build_manifest(
        self,
        asset: CuratedAsset,
        payload: dict[str, Any],
        payload_digest: str,
        actor: str,
        stamp: str,
    ) -> dict[str, Any]:
        """Wrap the payload using the canonical Knowledge Bubble builder.

        Falls back to a self-describing envelope only if the bubble module is not
        importable, so the Foundry never silently produces a divergent format
        while pretending it used the canonical one — the fallback declares itself
        via ``bubble_format_used``.
        """
        provenance = {
            "published_by": actor,
            "published_at": stamp,
            "payload_digest": payload_digest,
            "foundry_asset_format": ASSET_FORMAT,
            "foundry_asset_format_version": ASSET_FORMAT_VERSION,
        }
        try:
            from capt_solo.foundry.bubble import KnowledgeBubbleRuntime

            manifest = KnowledgeBubbleRuntime.build_bubble(
                asset.name,
                claims=[],
                skills=[],
                procedures=[],
                bubble_id=asset.asset_id,
                bubble_version=asset.asset_version,
                provenance=provenance,
                exported_namespaces=["capt_foundry"],
            )
            manifest["foundry_payload"] = payload
            manifest["foundry_payload_digest"] = payload_digest
            manifest["bubble_format_used"] = "capt_solo.foundry.bubble"
            manifest["manifest_hash"] = digest(
                {
                    "bubble_id": manifest.get("bubble_id"),
                    "bubble_version": manifest.get("bubble_version"),
                    "foundry_payload": payload,
                    "provenance": provenance,
                }
            )
            return manifest
        except ImportError:  # pragma: no cover - exercised by a dedicated test
            manifest = {
                "format": ASSET_FORMAT,
                "format_version": ASSET_FORMAT_VERSION,
                "bubble_id": asset.asset_id,
                "bubble_version": asset.asset_version,
                "name": asset.name,
                "bubble_format_used": "capt_foundry.fallback_envelope",
                "foundry_payload": payload,
                "foundry_payload_digest": payload_digest,
                "provenance": provenance,
            }
            manifest["manifest_hash"] = digest(
                {
                    "bubble_id": asset.asset_id,
                    "bubble_version": asset.asset_version,
                    "foundry_payload": payload,
                    "provenance": provenance,
                }
            )
            return manifest

    # -- retrieval ---------------------------------------------------------

    def get(self, asset_id: str) -> dict[str, Any] | None:
        row = self.store.conn.execute(
            "SELECT * FROM assets WHERE asset_id = ?", (asset_id,)
        ).fetchone()
        if row is None:
            return None
        out = dict(row)
        out["manifest"] = json.loads(out.pop("manifest_json"))
        out["entity_ids"] = json.loads(out["entity_ids"])
        out["corpus_ids"] = json.loads(out["corpus_ids"])
        out["evidence_ids"] = json.loads(out["evidence_ids"])
        return out

    def verify(self, asset_id: str) -> dict[str, Any]:
        """Recompute the payload digest from the stored manifest.

        Integrity check: proves the stored asset has not been altered in place.
        """
        stored = self.get(asset_id)
        if stored is None:
            raise DanglingReference(f"asset {asset_id} was never published")
        manifest = stored["manifest"]
        payload = manifest.get("foundry_payload")
        recomputed = digest(payload) if payload is not None else None
        return {
            "asset_id": asset_id,
            "payload_digest_matches": recomputed == manifest.get("foundry_payload_digest"),
            "stored_payload_digest": manifest.get("foundry_payload_digest"),
            "recomputed_payload_digest": recomputed,
            "manifest_hash": stored["manifest_hash"],
            "bubble_format_used": manifest.get("bubble_format_used"),
        }
