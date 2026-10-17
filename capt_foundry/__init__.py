"""CAPT Foundry — research asset curation layer (ADR-0130).

The Foundry gives durable identity to research-domain subjects and publishes
curated, provenance-preserving, replayable assets. It is a CONSUMER of CAPT
runtime primitives, not a runtime.

It does NOT own: evidence (``capt_runtime`` services + evidence contracts),
provenance (``capt_solo.memory.models`` / ``capt_solo.foundry.proof``), the event
ledger (``capt_runtime.store``, ADR-0104), governance
(``capt_runtime.authority``), or temporal ordering. It stores references into
those systems and never a parallel copy.

Every public entry point is a pure library over a caller-supplied SQLite
connection. There is no import-time construction, no global singleton, and no
service locator, so a runtime-owned service may construct the Foundry without
creating a second composition root.
"""

from __future__ import annotations

from capt_foundry.canonical import (
    FOUNDRY_SCHEMA_VERSION,
    canonical_json,
    digest,
    is_digest,
    is_rfc3339_z,
    normalize_name,
    utc_now,
)
from capt_foundry.corpus import CorpusManifest, CorpusRegistry, Document
from capt_foundry.entities import AliasRegistry, Entity, EntityAlias, EntityRegistry
from capt_foundry.errors import (
    AmbiguousAlias,
    DanglingReference,
    DuplicateIdentity,
    FoundryError,
    PathEscape,
    UnknownEntity,
    ValidationError,
)
from capt_foundry.projection import ObsidianProjection
from capt_foundry.publisher import ArtifactPublisher, CuratedAsset
from capt_foundry.seal_export import SealAssetExporter
from capt_foundry.storage import FoundryStore

__all__ = [
    "FOUNDRY_SCHEMA_VERSION",
    "canonical_json",
    "digest",
    "is_digest",
    "is_rfc3339_z",
    "normalize_name",
    "utc_now",
    "CorpusManifest",
    "CorpusRegistry",
    "Document",
    "AliasRegistry",
    "Entity",
    "EntityAlias",
    "EntityRegistry",
    "AmbiguousAlias",
    "DanglingReference",
    "DuplicateIdentity",
    "FoundryError",
    "PathEscape",
    "UnknownEntity",
    "ValidationError",
    "ObsidianProjection",
    "ArtifactPublisher",
    "CuratedAsset",
    "SealAssetExporter",
    "FoundryStore",
]
