"""End-to-end M0 asset lifecycle.

Proves the ONE complete lifecycle the M0 objective requires, as a single
continuous evidence chain rather than independent fragments:

    Approved source -> Entity/Alias registration -> Document metadata ingestion
    -> Corpus manifest -> Curated asset -> Provenance receipt
    -> Deterministic persistence -> Query/retrieval -> SEAL export
    -> Obsidian projection -> Replay and integrity verification

Replay is the load-bearing assertion: every digest must survive a process-level
restart against the same database file.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from capt_foundry import (
    AliasRegistry,
    CorpusRegistry,
    Entity,
    EntityAlias,
    EntityRegistry,
    FoundryStore,
)
from capt_foundry.corpus import index_directory
from capt_foundry.projection import ObsidianProjection
from capt_foundry.publisher import ArtifactPublisher, CuratedAsset
from capt_foundry.seal_export import SealAssetExporter

ACTOR = "human:captain"
STAMP = "2026-08-03T00:00:00Z"
REPO = Path(__file__).resolve().parents[2]


def _clock():
    return STAMP


def _wire(db_path):
    store = FoundryStore(db_path)
    entities = EntityRegistry(store, clock=_clock)
    aliases = AliasRegistry(store, entities, clock=_clock)
    corpora = CorpusRegistry(store, clock=_clock)
    publisher = ArtifactPublisher(store, entities, aliases, corpora, clock=_clock)
    exporter = SealAssetExporter(entities, aliases, corpora, clock=_clock)
    return store, entities, aliases, corpora, publisher, exporter


@pytest.fixture()
def source_dir(tmp_path):
    """An 'approved source': explicitly named files, no scanning."""
    d = tmp_path / "approved_source"
    d.mkdir()
    (d / "letter.txt").write_bytes(b"Notes on the Analytical Engine.")
    (d / "memoir.txt").write_bytes(b"Sketch of the Analytical Engine.")
    return d


def test_full_lifecycle(tmp_path, source_dir):
    db = tmp_path / "foundry.db"
    vault = tmp_path / "vault"
    vault.mkdir()

    store, entities, aliases, corpora, publisher, exporter = _wire(db)

    # 1. Entity + alias registration
    entities.register(
        Entity(entity_id="e.ada", entity_type="person", canonical_name="Ada Lovelace",
               description="Mathematician.", evidence_ids=["ev.letter.1"]),
        ACTOR,
    )
    aliases.register(
        EntityAlias(alias_id="al.1", entity_id="e.ada", alias="A. A. Lovelace",
                    confidence="evidence_backed", evidence_ids=["ev.letter.1"]),
        ACTOR,
    )
    assert aliases.resolve("a. a. lovelace")["entity_id"] == "e.ada"

    # 2. Document metadata ingestion -> corpus manifest
    manifest = index_directory(
        "c.notes", "Analytical Engine notes", source_dir,
        relative_paths=["letter.txt", "memoir.txt"], root_label="approved_source",
    )
    corpora.register(manifest, ACTOR)
    corpus_digest = manifest.manifest_digest()
    assert corpora.require("c.notes")["manifest_digest"] == corpus_digest

    # 3. Curated asset publication + provenance receipt
    published = publisher.publish(
        CuratedAsset(asset_id="asset.ada", name="Ada Lovelace dossier",
                     entity_ids=["e.ada"], corpus_ids=["c.notes"],
                     evidence_ids=["ev.letter.1"], summary="M0 lifecycle proof."),
        ACTOR, published_at=STAMP,
    )
    manifest_hash = published["manifest_hash"]
    assert published["bubble_format_used"] == "capt_solo.foundry.bubble"
    assert published["provenance"]["published_by"] == ACTOR

    # 4. Query / retrieval
    assert publisher.get("asset.ada")["entity_ids"] == ["e.ada"]

    # 5. SEAL export
    envelope = exporter.export(exported_at=STAMP)
    assert SealAssetExporter.verify(envelope)["matches"] is True
    export_digest = envelope["content_digest"]

    # 6. Obsidian projection
    proj = ObsidianProjection(vault)
    note = proj.project_asset(published)
    index = proj.project_index([published])
    assert note.read_text(encoding="utf-8").count("Ada Lovelace") >= 1
    assert "asset.ada" in index.read_text(encoding="utf-8")

    # 7. Integrity verification
    assert publisher.verify("asset.ada")["payload_digest_matches"] is True
    store.close()

    # 8. REPLAY in a genuinely fresh PROCESS against the same database.
    replay = subprocess.run(
        [sys.executable, str(REPO / "tests" / "capt_foundry" / "_replay_probe.py"), str(db)],
        capture_output=True, text=True, cwd=str(REPO), check=False,
    )
    assert replay.returncode == 0, replay.stderr
    out = json.loads(replay.stdout)
    assert out["manifest_hash"] == manifest_hash
    assert out["corpus_digest"] == corpus_digest
    assert out["export_digest"] == export_digest
    assert out["payload_digest_matches"] is True
    assert out["alias_resolves"] == "e.ada"

    # 9. Projection from the replayed manifest is byte-identical.
    proj2 = ObsidianProjection(vault)
    assert proj2.render_asset(out["manifest"]) == note.read_text(encoding="utf-8")


def test_lifecycle_is_reproducible_from_scratch(tmp_path, source_dir):
    """Two independent runs over identical inputs produce identical digests."""
    results = []
    for name in ("run_a", "run_b"):
        db = tmp_path / (f"{name}.db")
        store, entities, _aliases, corpora, publisher, exporter = _wire(db)
        entities.register(
            Entity(entity_id="e.ada", entity_type="person", canonical_name="Ada Lovelace"), ACTOR
        )
        corpora.register(
            index_directory("c.notes", "Notes", source_dir,
                            relative_paths=["letter.txt"], root_label="approved_source"),
            ACTOR,
        )
        m = publisher.publish(
            CuratedAsset(asset_id="asset.ada", name="Dossier", entity_ids=["e.ada"],
                         corpus_ids=["c.notes"]),
            ACTOR, published_at=STAMP,
        )
        results.append((m["manifest_hash"], exporter.export(exported_at=STAMP)["content_digest"]))
        store.close()
    assert results[0] == results[1]


def test_stale_corpus_is_visible_in_export(tmp_path, source_dir):
    """Never silently trust stale material: freshness must reach the consumer."""
    db = tmp_path / "foundry.db"
    store, _entities, _aliases, corpora, _publisher, exporter = _wire(db)
    corpora.register(
        index_directory("c.notes", "Notes", source_dir,
                        relative_paths=["letter.txt"], root_label="approved_source"),
        ACTOR,
    )
    corpora.mark_stale("c.notes")
    assert exporter.export(exported_at=STAMP)["corpora"][0]["freshness"] == "stale"
    store.close()


def test_changed_source_is_detected(tmp_path, source_dir):
    """Never lose a source hash: re-indexing detects a mutated document."""
    db = tmp_path / "foundry.db"
    store, _entities, _aliases, corpora, _publisher, _exporter = _wire(db)
    corpora.register(
        index_directory("c.notes", "Notes", source_dir,
                        relative_paths=["letter.txt"], root_label="approved_source"),
        ACTOR,
    )
    (source_dir / "letter.txt").write_bytes(b"TAMPERED CONTENT")
    report = corpora.verify_against_manifest(
        index_directory("c.notes", "Notes", source_dir,
                        relative_paths=["letter.txt"], root_label="approved_source")
    )
    assert report["matches"] is False
    assert report["changed"] == ["c.notes.d0000"]
    store.close()
