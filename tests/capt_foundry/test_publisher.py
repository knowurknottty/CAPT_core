"""Publisher: bubble reuse, dangling-reference refusal, determinism, integrity."""

from __future__ import annotations

import pytest

from capt_foundry import Entity, EntityAlias
from capt_foundry.canonical import digest_bytes
from capt_foundry.corpus import CorpusManifest, Document
from capt_foundry.errors import DanglingReference, DuplicateIdentity, ValidationError
from capt_foundry.publisher import ASSET_FORMAT, CuratedAsset

ACTOR = "human:captain"
STAMP = "2026-08-03T00:00:00Z"


@pytest.fixture()
def seeded(entities, aliases, corpora):
    entities.register(
        Entity(entity_id="e.ada", entity_type="person", canonical_name="Ada Lovelace",
               evidence_ids=["ev.1"]),
        ACTOR,
    )
    aliases.register(
        EntityAlias(alias_id="a.1", entity_id="e.ada", alias="A. Lovelace",
                    confidence="evidence_backed", evidence_ids=["ev.1"]),
        ACTOR,
    )
    corpora.register(
        CorpusManifest(
            corpus_id="c.1", name="Notes", root_label="fixtures",
            documents=[Document(document_id="c.1.d0", relative_path="a.txt",
                                content_digest=digest_bytes(b"alpha"), byte_size=5)],
        ),
        ACTOR,
    )
    return True


def _asset():
    return CuratedAsset(
        asset_id="asset.1", name="Ada dossier", entity_ids=["e.ada"],
        corpus_ids=["c.1"], evidence_ids=["ev.1"], summary="Test asset.",
    )


# -- validation -------------------------------------------------------------


def test_asset_requires_a_reference():
    with pytest.raises(ValidationError):
        CuratedAsset(asset_id="a.1", name="Empty")


def test_asset_rejects_bad_id():
    with pytest.raises(ValidationError):
        CuratedAsset(asset_id="bad id", name="X", entity_ids=["e.1"])


def test_publish_requires_actor(publisher, seeded):
    with pytest.raises(ValidationError):
        publisher.publish(_asset(), "")


# -- dangling references ----------------------------------------------------


def test_dangling_entity_refused(publisher):
    with pytest.raises(DanglingReference):
        publisher.publish(CuratedAsset(asset_id="a.1", name="X", entity_ids=["e.ghost"]), ACTOR)


def test_dangling_corpus_refused(publisher, seeded):
    with pytest.raises(DanglingReference):
        publisher.publish(CuratedAsset(asset_id="a.1", name="X", corpus_ids=["c.ghost"]), ACTOR)


# -- payload ----------------------------------------------------------------


def test_payload_preserves_provenance(publisher, seeded):
    p = publisher.build_payload(_asset())
    ent = p["entities"][0]
    assert ent["provenance"]["registered_by"] == ACTOR
    assert ent["provenance"]["registered_at"] == STAMP
    assert ent["record_digest"].startswith("sha256:")
    assert p["corpora"][0]["documents"][0]["content_digest"].startswith("sha256:")


def test_payload_includes_aliases(publisher, seeded):
    p = publisher.build_payload(_asset())
    assert p["entities"][0]["aliases"][0]["alias"] == "A. Lovelace"
    assert p["entities"][0]["aliases"][0]["confidence"] == "evidence_backed"


def test_payload_evidence_are_references_only(publisher, seeded):
    """Foundry must not carry evidence bodies or verification verdicts."""
    p = publisher.build_payload(_asset())
    assert p["evidence_refs"] == ["ev.1"]
    flat = str(p).lower()
    for forbidden in ("verified", "verification_status", "guardverdict", "promotionstate"):
        assert forbidden not in flat


def test_payload_is_deterministic(publisher, seeded):
    assert publisher.build_payload(_asset()) == publisher.build_payload(_asset())


# -- publication ------------------------------------------------------------


def test_publish_uses_canonical_bubble_format(publisher, seeded):
    m = publisher.publish(_asset(), ACTOR, published_at=STAMP)
    assert m["bubble_format_used"] == "capt_solo.foundry.bubble"
    assert m["manifest_hash"].startswith("sha256:")
    assert m["foundry_payload"]["format"] == ASSET_FORMAT


def test_publish_is_recorded_and_retrievable(publisher, seeded):
    publisher.publish(_asset(), ACTOR, published_at=STAMP)
    stored = publisher.get("asset.1")
    assert stored["published_by"] == ACTOR
    assert stored["entity_ids"] == ["e.ada"]


def test_republication_is_deterministic(publisher, seeded):
    m1 = publisher.publish(_asset(), ACTOR, published_at=STAMP)
    m2 = publisher.publish(_asset(), ACTOR, published_at=STAMP)
    assert m1["manifest_hash"] == m2["manifest_hash"]


def test_conflicting_republication_refused(publisher, seeded, entities):
    publisher.publish(_asset(), ACTOR, published_at=STAMP)
    entities.register(
        Entity(entity_id="e.cb", entity_type="person", canonical_name="Charles Babbage"), ACTOR
    )
    changed = CuratedAsset(
        asset_id="asset.1", name="Ada dossier", entity_ids=["e.ada", "e.cb"],
        corpus_ids=["c.1"], evidence_ids=["ev.1"], summary="Test asset.",
    )
    with pytest.raises(DuplicateIdentity):
        publisher.publish(changed, ACTOR, published_at=STAMP)


def test_manifest_hash_changes_with_content(publisher, seeded, entities):
    m1 = publisher.publish(_asset(), ACTOR, published_at=STAMP)
    entities.register(
        Entity(entity_id="e.cb", entity_type="person", canonical_name="Charles Babbage"), ACTOR
    )
    m2 = publisher.publish(
        CuratedAsset(asset_id="asset.2", name="Two", entity_ids=["e.ada", "e.cb"]),
        ACTOR, published_at=STAMP,
    )
    assert m1["manifest_hash"] != m2["manifest_hash"]


# -- integrity --------------------------------------------------------------


def test_verify_detects_intact_asset(publisher, seeded):
    publisher.publish(_asset(), ACTOR, published_at=STAMP)
    assert publisher.verify("asset.1")["payload_digest_matches"] is True


def test_verify_detects_tampering(publisher, seeded):
    publisher.publish(_asset(), ACTOR, published_at=STAMP)
    conn = publisher.store.conn
    row = conn.execute("SELECT manifest_json FROM assets WHERE asset_id='asset.1'").fetchone()
    tampered = row["manifest_json"].replace("Ada Lovelace", "Someone Else")
    conn.execute("UPDATE assets SET manifest_json=? WHERE asset_id='asset.1'", (tampered,))
    conn.commit()
    assert publisher.verify("asset.1")["payload_digest_matches"] is False


def test_verify_unknown_asset_raises(publisher):
    with pytest.raises(DanglingReference):
        publisher.verify("asset.nope")


def test_no_runtime_construction_during_publish(publisher, seeded, monkeypatch):
    """The publisher must call build_bubble statically, never instantiate the runtime.

    Instantiating a canonical subsystem here would be a parallel construction
    path and would violate the composition-root invariant (ADR-0130).
    """
    from capt_solo.foundry import bubble as bubble_mod

    def explode(*a, **k):
        raise AssertionError("KnowledgeBubbleRuntime was instantiated by the publisher")

    monkeypatch.setattr(bubble_mod.KnowledgeBubbleRuntime, "__init__", explode)
    m = publisher.publish(_asset(), ACTOR, published_at=STAMP)
    assert m["bubble_format_used"] == "capt_solo.foundry.bubble"
