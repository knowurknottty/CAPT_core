"""Obsidian projection: determinism, idempotence, and write-path containment."""

from __future__ import annotations

import os

import pytest

from capt_foundry import Entity, EntityAlias
from capt_foundry.canonical import digest_bytes
from capt_foundry.corpus import CorpusManifest, Document
from capt_foundry.errors import PathEscape, ValidationError
from capt_foundry.projection import ObsidianProjection, sanitize_filename
from capt_foundry.publisher import CuratedAsset

ACTOR = "human:captain"
STAMP = "2026-08-03T00:00:00Z"


@pytest.fixture()
def manifest(publisher, entities, aliases, corpora):
    entities.register(
        Entity(entity_id="e.ada", entity_type="person", canonical_name="Ada Lovelace",
               description="Mathematician.", evidence_ids=["ev.1"]),
        ACTOR,
    )
    aliases.register(EntityAlias(alias_id="a.1", entity_id="e.ada", alias="A. Lovelace"), ACTOR)
    corpora.register(
        CorpusManifest(corpus_id="c.1", name="Notes", root_label="fixtures",
                       documents=[Document(document_id="c.1.d0", relative_path="a.txt",
                                           content_digest=digest_bytes(b"alpha"), byte_size=5)]),
        ACTOR,
    )
    return publisher.publish(
        CuratedAsset(asset_id="asset.1", name="Ada dossier", entity_ids=["e.ada"],
                     corpus_ids=["c.1"], evidence_ids=["ev.1"], summary="Test."),
        ACTOR, published_at=STAMP,
    )


# -- filename sanitization --------------------------------------------------


@pytest.mark.parametrize(
    "hostile",
    ["../../etc/passwd", "a/b", "a\\b", "con", "COM1", "  ", "...", "x" * 400,
     "note\x00.md", "a:b|c?d*e"],
)
def test_sanitize_never_returns_a_path_or_reserved_name(hostile):
    out = sanitize_filename(hostile)
    assert "/" not in out and "\\" not in out
    assert out not in ("", ".", "..")
    assert not out.startswith(".")
    assert len(out) <= 121
    assert "\x00" not in out


def test_sanitize_is_deterministic():
    assert sanitize_filename("Ada Lovelace") == sanitize_filename("Ada Lovelace")


# -- construction safety ----------------------------------------------------


def test_missing_vault_root_refused(tmp_path):
    with pytest.raises(ValidationError):
        ObsidianProjection(tmp_path / "nope")


def test_file_as_vault_root_refused(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("x")
    with pytest.raises(ValidationError):
        ObsidianProjection(f)


def test_symlinked_vault_root_refused(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    try:
        os.symlink(real, link)
    except (OSError, NotImplementedError):  # pragma: no cover
        pytest.skip("symlinks unavailable")
    with pytest.raises(PathEscape):
        ObsidianProjection(link)


def test_traversal_subdir_is_sanitized_not_escaped(tmp_path):
    """A hostile subdir name must be neutralised, never followed."""
    proj = ObsidianProjection(tmp_path, subdir="../escape")
    assert proj.target_dir.resolve().parent == tmp_path.resolve()


# -- rendering --------------------------------------------------------------


def test_render_is_deterministic(tmp_path, manifest):
    proj = ObsidianProjection(tmp_path)
    assert proj.render_asset(manifest) == proj.render_asset(manifest)


def test_render_contains_provenance_and_digests(tmp_path, manifest):
    md = ObsidianProjection(tmp_path).render_asset(manifest)
    assert "Ada Lovelace" in md
    assert "capt_manifest_hash:" in md
    assert "capt_published_by:" in md
    assert manifest["foundry_payload_digest"] in md
    assert "derived-read-only" in md


def test_render_declares_evidence_ownership(tmp_path, manifest):
    """The note must not let a reader mistake a reference for proof."""
    md = ObsidianProjection(tmp_path).render_asset(manifest)
    assert "owned by the CAPT runtime" in md
    assert "references, not proof" in md


def test_render_escapes_frontmatter_quotes(tmp_path, manifest):
    manifest = dict(manifest)
    manifest["provenance"] = dict(manifest["provenance"])
    manifest["provenance"]["published_by"] = 'evil" \ninjected: true'
    md = ObsidianProjection(tmp_path).render_asset(manifest)
    header = md.split("---")[1]
    assert "\ninjected: true" not in header


# -- writing ----------------------------------------------------------------


def test_project_writes_inside_root(tmp_path, manifest):
    proj = ObsidianProjection(tmp_path)
    path = proj.project_asset(manifest)
    assert path.exists()
    assert path.resolve().is_relative_to(tmp_path.resolve())
    assert path.suffix == ".md"


def test_projection_is_idempotent(tmp_path, manifest):
    proj = ObsidianProjection(tmp_path)
    p1 = proj.project_asset(manifest)
    first = p1.read_text(encoding="utf-8")
    mtime = p1.stat().st_mtime_ns
    p2 = proj.project_asset(manifest)
    assert p1 == p2
    assert p2.read_text(encoding="utf-8") == first
    assert p2.stat().st_mtime_ns == mtime  # unchanged content -> no rewrite


def test_hostile_asset_name_cannot_escape(tmp_path, publisher, entities):
    entities.register(
        Entity(entity_id="e.x", entity_type="person", canonical_name="X"), ACTOR
    )
    m = publisher.publish(
        CuratedAsset(asset_id="asset.evil", name="../../../../etc/passwd",
                     entity_ids=["e.x"]),
        ACTOR, published_at=STAMP,
    )
    proj = ObsidianProjection(tmp_path)
    path = proj.project_asset(m)
    assert path.resolve().is_relative_to(tmp_path.resolve())
    assert not (tmp_path.parent / "etc").exists()


def test_explicit_filename_with_separator_refused(tmp_path, manifest):
    proj = ObsidianProjection(tmp_path)
    with pytest.raises(PathEscape):
        proj.project_asset(manifest, filename="sub/evil.md")


def test_projection_never_deletes(tmp_path, manifest):
    proj = ObsidianProjection(tmp_path)
    keep = proj.target_dir / "human-note.md"
    keep.write_text("hand written", encoding="utf-8")
    proj.project_asset(manifest)
    proj.project_index([manifest])
    assert keep.read_text(encoding="utf-8") == "hand written"


def test_index_lists_assets(tmp_path, manifest):
    proj = ObsidianProjection(tmp_path)
    idx = proj.project_index([manifest])
    text = idx.read_text(encoding="utf-8")
    assert "asset.1" in text
    assert manifest["manifest_hash"] in text


def test_index_is_idempotent(tmp_path, manifest):
    proj = ObsidianProjection(tmp_path)
    a = proj.project_index([manifest]).read_text(encoding="utf-8")
    b = proj.project_index([manifest]).read_text(encoding="utf-8")
    assert a == b


def test_empty_index_is_valid(tmp_path):
    proj = ObsidianProjection(tmp_path)
    assert "_none_" in proj.project_index([]).read_text(encoding="utf-8")
