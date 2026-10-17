"""Entity and alias registry behaviour, including the refusal-to-guess rule."""

from __future__ import annotations

import pytest

from capt_foundry import Entity, EntityAlias
from capt_foundry.entities import AliasRegistry, EntityRegistry
from capt_foundry.errors import (
    AmbiguousAlias,
    DuplicateIdentity,
    UnknownEntity,
    ValidationError,
)
from capt_foundry.storage import FoundryStore

ACTOR = "human:captain"


def _ada():
    return Entity(entity_id="e.ada", entity_type="person", canonical_name="Ada Lovelace")


def _babbage():
    return Entity(entity_id="e.cb", entity_type="person", canonical_name="Charles Babbage")


# -- validation -------------------------------------------------------------


def test_entity_rejects_bad_id():
    with pytest.raises(ValidationError):
        Entity(entity_id="has space", entity_type="person", canonical_name="X")


def test_entity_rejects_unknown_type():
    with pytest.raises(ValidationError):
        Entity(entity_id="e.1", entity_type="alien", canonical_name="X")


def test_entity_rejects_empty_name():
    with pytest.raises(ValidationError):
        Entity(entity_id="e.1", entity_type="person", canonical_name="   ")


def test_superseded_by_requires_superseded_status():
    with pytest.raises(ValidationError):
        Entity(
            entity_id="e.1", entity_type="person", canonical_name="X",
            status="active", superseded_by="e.2",
        )


def test_alias_evidence_backed_requires_evidence():
    with pytest.raises(ValidationError) as ei:
        EntityAlias(alias_id="a.1", entity_id="e.1", alias="X", confidence="evidence_backed")
    assert "requires evidence_ids" in str(ei.value)


def test_register_requires_actor(entities):
    with pytest.raises(ValidationError):
        entities.register(_ada(), "")


# -- registration -----------------------------------------------------------


def test_register_and_get(entities):
    entities.register(_ada(), ACTOR)
    row = entities.require("e.ada")
    assert row["canonical_name"] == "Ada Lovelace"
    assert row["normalized_name"] == "ada lovelace"
    assert row["registered_by"] == ACTOR
    assert row["record_digest"].startswith("sha256:")


def test_registration_is_idempotent_for_identical_content(entities):
    entities.register(_ada(), ACTOR)
    entities.register(_ada(), ACTOR)  # no raise
    assert len(entities.all()) == 1


def test_duplicate_id_with_different_content_is_refused(entities):
    entities.register(_ada(), ACTOR)
    with pytest.raises(DuplicateIdentity):
        entities.register(
            Entity(entity_id="e.ada", entity_type="person", canonical_name="Someone Else"),
            ACTOR,
        )


def test_require_unknown_entity_raises(entities):
    with pytest.raises(UnknownEntity):
        entities.require("e.nope")


def test_record_digest_is_deterministic(entities):
    entities.register(_ada(), ACTOR)
    assert entities.require("e.ada")["record_digest"] == _ada().digest()


# -- aliases ----------------------------------------------------------------


def test_alias_resolution(entities, aliases):
    entities.register(_ada(), ACTOR)
    aliases.register(EntityAlias(alias_id="a.1", entity_id="e.ada", alias="A. Lovelace"), ACTOR)
    assert aliases.resolve("a. lovelace")["entity_id"] == "e.ada"
    assert aliases.resolve("  A.   LOVELACE  ")["entity_id"] == "e.ada"


def test_canonical_name_also_resolves(entities, aliases):
    entities.register(_ada(), ACTOR)
    assert aliases.resolve("Ada Lovelace")["entity_id"] == "e.ada"


def test_alias_to_unknown_entity_is_refused(aliases):
    with pytest.raises(UnknownEntity):
        aliases.register(EntityAlias(alias_id="a.1", entity_id="e.ghost", alias="X"), ACTOR)


def test_ambiguous_alias_refuses_to_guess(entities, aliases):
    """The core anti-false-join rule: two entities, one name, no guess."""
    entities.register(_ada(), ACTOR)
    entities.register(_babbage(), ACTOR)
    aliases.register(EntityAlias(alias_id="a.1", entity_id="e.ada", alias="The Pioneer"), ACTOR)
    aliases.register(EntityAlias(alias_id="a.2", entity_id="e.cb", alias="The Pioneer"), ACTOR)
    with pytest.raises(AmbiguousAlias) as ei:
        aliases.resolve("the pioneer")
    assert ei.value.candidates == ["e.ada", "e.cb"]
    assert len(aliases.candidates("The Pioneer")) == 2


def test_duplicate_alias_on_same_entity_refused(entities, aliases):
    entities.register(_ada(), ACTOR)
    aliases.register(EntityAlias(alias_id="a.1", entity_id="e.ada", alias="AL"), ACTOR)
    with pytest.raises(DuplicateIdentity):
        aliases.register(EntityAlias(alias_id="a.2", entity_id="e.ada", alias="al"), ACTOR)


def test_alias_registration_idempotent(entities, aliases):
    entities.register(_ada(), ACTOR)
    a = EntityAlias(alias_id="a.1", entity_id="e.ada", alias="AL")
    aliases.register(a, ACTOR)
    aliases.register(a, ACTOR)
    assert len(aliases.aliases_for("e.ada")) == 1


def test_distinct_names_do_not_collapse(entities, aliases):
    entities.register(_ada(), ACTOR)
    entities.register(_babbage(), ACTOR)
    aliases.register(EntityAlias(alias_id="a.1", entity_id="e.ada", alias="Müller"), ACTOR)
    aliases.register(EntityAlias(alias_id="a.2", entity_id="e.cb", alias="Muller"), ACTOR)
    assert aliases.resolve("Müller")["entity_id"] == "e.ada"
    assert aliases.resolve("Muller")["entity_id"] == "e.cb"


def test_evidence_backed_alias_carries_refs(entities, aliases):
    entities.register(_ada(), ACTOR)
    aliases.register(
        EntityAlias(
            alias_id="a.1", entity_id="e.ada", alias="AAL",
            confidence="evidence_backed", evidence_ids=["ev.1"],
        ),
        ACTOR,
    )
    assert aliases.aliases_for("e.ada")[0]["evidence_ids"] == ["ev.1"]


# -- merge ------------------------------------------------------------------


def test_merge_supersedes_and_repoints_aliases(entities, aliases):
    entities.register(_ada(), ACTOR)
    entities.register(
        Entity(entity_id="e.ada2", entity_type="person", canonical_name="Ada Byron"), ACTOR
    )
    aliases.register(EntityAlias(alias_id="a.1", entity_id="e.ada2", alias="Countess"), ACTOR)
    entities.merge("e.ada2", "e.ada", ACTOR)

    assert entities.require("e.ada2")["status"] == "superseded"
    # The old name still resolves — to the surviving entity.
    assert aliases.resolve("Countess")["entity_id"] == "e.ada"
    assert aliases.resolve("Ada Byron")["entity_id"] == "e.ada"


def test_merge_into_self_refused(entities):
    entities.register(_ada(), ACTOR)
    with pytest.raises(ValidationError):
        entities.merge("e.ada", "e.ada", ACTOR)


def test_merge_unknown_refused(entities):
    entities.register(_ada(), ACTOR)
    with pytest.raises(UnknownEntity):
        entities.merge("e.ghost", "e.ada", ACTOR)


def test_supersede_cycle_does_not_hang(entities, aliases):
    """A corrupted cycle must terminate, not spin forever."""
    entities.register(_ada(), ACTOR)
    entities.register(_babbage(), ACTOR)
    conn = entities.store.conn
    conn.execute("UPDATE entities SET status='superseded', superseded_by='e.cb' WHERE entity_id='e.ada'")
    conn.execute("UPDATE entities SET status='superseded', superseded_by='e.ada' WHERE entity_id='e.cb'")
    conn.commit()
    assert aliases.candidates("Ada Lovelace") == []


# -- durability -------------------------------------------------------------


def test_state_survives_reconnect(tmp_path):
    """Replay: a fresh connection to the same file sees identical records."""
    db = tmp_path / "foundry.db"
    s1 = FoundryStore(db)
    e1 = EntityRegistry(s1)
    a1 = AliasRegistry(s1, e1)
    e1.register(_ada(), ACTOR)
    a1.register(EntityAlias(alias_id="a.1", entity_id="e.ada", alias="AL"), ACTOR)
    digest_before = e1.require("e.ada")["record_digest"]
    s1.close()

    s2 = FoundryStore(db)
    e2 = EntityRegistry(s2)
    a2 = AliasRegistry(s2, e2)
    assert e2.require("e.ada")["record_digest"] == digest_before
    assert a2.resolve("AL")["entity_id"] == "e.ada"
    s2.close()
