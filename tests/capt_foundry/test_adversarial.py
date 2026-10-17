"""Adversarial pass: deliberate attempts to BREAK the Foundry's guarantees.

These are not happy-path tests. Each one is an attack that would falsify a claim
made in ADR-0130 if it succeeded. A regression here means a stated guarantee is
no longer true.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from capt_foundry import Entity, EntityAlias, FoundryStore
from capt_foundry.canonical import digest, digest_bytes
from capt_foundry.corpus import CorpusManifest, Document
from capt_foundry.errors import (
    AmbiguousAlias,
    DanglingReference,
    PathEscape,
    ValidationError,
)
from capt_foundry.projection import ObsidianProjection
from capt_foundry.publisher import CuratedAsset
from capt_foundry.seal_export import _scan_forbidden

ACTOR = "human:captain"
STAMP = "2026-08-03T00:00:00Z"
REPO = Path(__file__).resolve().parents[2]


# -- attack: SQL injection through identifiers ------------------------------


def test_sql_injection_via_entity_id_is_impossible(entities):
    """Identifier pattern blocks it; parameter binding blocks it again."""
    with pytest.raises(ValidationError):
        Entity(entity_id="e.1'; DROP TABLE entities;--", entity_type="person",
               canonical_name="X")


def test_sql_injection_via_name_is_bound_not_interpolated(entities):
    """A hostile NAME is legal input and must be stored literally, not executed."""
    hostile = "Robert'); DROP TABLE entities;--"
    entities.register(
        Entity(entity_id="e.bobby", entity_type="person", canonical_name=hostile), ACTOR
    )
    assert entities.require("e.bobby")["canonical_name"] == hostile
    # Table still exists and is queryable.
    assert len(entities.all()) == 1


def test_sql_injection_via_alias_lookup(entities, aliases):
    entities.register(Entity(entity_id="e.1", entity_type="person", canonical_name="X"), ACTOR)
    hostile = "' OR '1'='1"
    with pytest.raises(Exception) as ei:
        aliases.resolve(hostile)
    # Must be a clean not-found, never a wildcard match.
    assert "no entity resolves" in str(ei.value)


# -- attack: forge an asset that looks verified -----------------------------


def test_foundry_cannot_mint_a_verification_verdict(publisher, entities):
    """The Foundry must have no API that asserts evidence is verified."""
    entities.register(Entity(entity_id="e.1", entity_type="person", canonical_name="X"), ACTOR)
    m = publisher.publish(
        CuratedAsset(asset_id="a.1", name="X", entity_ids=["e.1"], evidence_ids=["ev.1"]),
        ACTOR, published_at=STAMP,
    )
    payload = m["foundry_payload"]
    assert payload["evidence_refs"] == ["ev.1"]
    assert "verification" not in payload
    assert "verified" not in str(payload).lower()
    # No public method exists to set one.
    for attr in dir(publisher):
        assert "verif" not in attr.lower() or attr == "verify"


def test_publisher_verify_is_integrity_not_evidence_verification(publisher, entities):
    """`verify` must mean 'digest intact', never 'claim is true'."""
    entities.register(Entity(entity_id="e.1", entity_type="person", canonical_name="X"), ACTOR)
    publisher.publish(CuratedAsset(asset_id="a.1", name="X", entity_ids=["e.1"]),
                      ACTOR, published_at=STAMP)
    result = publisher.verify("a.1")
    assert set(result) == {
        "asset_id", "payload_digest_matches", "stored_payload_digest",
        "recomputed_payload_digest", "manifest_hash", "bubble_format_used",
    }
    assert "claim" not in str(result).lower()


# -- attack: silent duplicate / false join ----------------------------------


def test_two_entities_same_name_do_not_silently_merge(entities, aliases):
    entities.register(Entity(entity_id="e.1", entity_type="person", canonical_name="John Smith"), ACTOR)
    entities.register(Entity(entity_id="e.2", entity_type="person", canonical_name="John Smith"), ACTOR)
    with pytest.raises(AmbiguousAlias):
        aliases.resolve("John Smith")


def test_ambiguity_survives_alias_indirection(entities, aliases):
    """Ambiguity introduced via aliases must not be resolved by luck of ordering."""
    entities.register(Entity(entity_id="e.1", entity_type="person", canonical_name="Alpha"), ACTOR)
    entities.register(Entity(entity_id="e.2", entity_type="person", canonical_name="Beta"), ACTOR)
    aliases.register(EntityAlias(alias_id="a.1", entity_id="e.1", alias="Shared"), ACTOR)
    aliases.register(EntityAlias(alias_id="a.2", entity_id="e.2", alias="Shared"), ACTOR)
    for _ in range(5):
        with pytest.raises(AmbiguousAlias):
            aliases.resolve("shared")


def test_alias_pointing_at_superseded_entity_does_not_double_count(entities, aliases):
    """After a merge, the same name must resolve to ONE surviving entity."""
    entities.register(Entity(entity_id="e.1", entity_type="person", canonical_name="Alpha"), ACTOR)
    entities.register(Entity(entity_id="e.2", entity_type="person", canonical_name="Alpha Two"), ACTOR)
    aliases.register(EntityAlias(alias_id="a.1", entity_id="e.2", alias="Shared"), ACTOR)
    aliases.register(EntityAlias(alias_id="a.2", entity_id="e.1", alias="Shared2"), ACTOR)
    entities.merge("e.2", "e.1", ACTOR)
    assert aliases.resolve("Shared")["entity_id"] == "e.1"
    assert len(aliases.candidates("Shared")) == 1


# -- attack: tamper with persisted state ------------------------------------


def test_direct_db_tampering_is_detected_by_verify(publisher, entities):
    entities.register(Entity(entity_id="e.1", entity_type="person", canonical_name="X"), ACTOR)
    publisher.publish(CuratedAsset(asset_id="a.1", name="X", entity_ids=["e.1"]),
                      ACTOR, published_at=STAMP)
    conn = publisher.store.conn
    row = conn.execute("SELECT manifest_json FROM assets WHERE asset_id='a.1'").fetchone()
    conn.execute(
        "UPDATE assets SET manifest_json=? WHERE asset_id='a.1'",
        (row["manifest_json"].replace('"X"', '"Tampered"'),),
    )
    conn.commit()
    assert publisher.verify("a.1")["payload_digest_matches"] is False


def test_entity_record_digest_detects_out_of_band_edit(entities):
    entities.register(Entity(entity_id="e.1", entity_type="person", canonical_name="Original"), ACTOR)
    stored = entities.require("e.1")["record_digest"]
    entities.store.conn.execute("UPDATE entities SET canonical_name='Hacked' WHERE entity_id='e.1'")
    entities.store.conn.commit()
    row = entities.require("e.1")
    recomputed = digest({
        "entity_id": row["entity_id"], "entity_type": row["entity_type"],
        "canonical_name": row["canonical_name"], "normalized_name": row["normalized_name"],
        "description": row["description"], "evidence_ids": row["evidence_ids"],
        "attributes": row["attributes"], "status": row["status"],
        "superseded_by": row["superseded_by"],
    })
    assert recomputed != stored  # the stored digest no longer matches the row


# -- attack: schema confusion ------------------------------------------------


def test_foreign_schema_version_is_refused(tmp_path):
    db = tmp_path / "alien.db"
    s = FoundryStore(db)
    s.close()
    conn = sqlite3.connect(db)
    conn.execute("UPDATE foundry_schema_version SET version='capt-foundry.v99'")
    conn.commit()
    conn.close()
    with pytest.raises(ValidationError) as ei:
        FoundryStore(db)
    assert "migration is required" in str(ei.value)


def test_foreign_key_enforcement_blocks_orphan_alias(store, entities):
    """DB-level guard, not just the Python check."""
    with pytest.raises(sqlite3.IntegrityError):
        store.conn.execute(
            "INSERT INTO entity_aliases (alias_id, entity_id, alias, normalized_alias,"
            " alias_kind, confidence, evidence_ids, record_digest, registered_by,"
            " registered_at) VALUES ('a.x','e.ghost','X','x','also_known_as',"
            "'asserted','[]','sha256:0','a','t')"
        )


# -- attack: escape the vault -----------------------------------------------


@pytest.mark.parametrize("evil", ["../evil.md", "../../evil.md", "sub/evil.md", "/tmp/evil.md"])
def test_projection_filename_escapes_all_refused(tmp_path, evil):
    proj = ObsidianProjection(tmp_path)
    with pytest.raises(PathEscape):
        proj.project_asset({"foundry_payload": {"name": "x"}}, filename=evil)


def test_projection_cannot_overwrite_via_symlink(tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("precious", encoding="utf-8")
    vault = tmp_path / "vault"
    vault.mkdir()
    proj = ObsidianProjection(vault)
    try:
        os.symlink(outside, proj.target_dir / "asset.md")
    except (OSError, NotImplementedError):  # pragma: no cover
        pytest.skip("symlinks unavailable")
    with pytest.raises(PathEscape):
        proj.project_asset({"foundry_payload": {"name": "x"}}, filename="asset.md")
    assert outside.read_text(encoding="utf-8") == "precious"


def test_store_path_escape_refused(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(PathEscape):
        FoundryStore(root / ".." / "escape.db", allowed_root=root)


# -- attack: smuggle SEAL concepts through free-text fields -----------------


def test_seal_concepts_in_values_do_not_create_forbidden_keys(exporter, entities):
    """A hostile description must not be able to inject a SEAL-owned KEY."""
    entities.register(
        Entity(entity_id="e.1", entity_type="person", canonical_name="X",
               description="prompt: submit this case to the reviewer",
               attributes={"note": "ruleset candidate submission"}),
        ACTOR,
    )
    env = exporter.export(exported_at=STAMP)
    assert _scan_forbidden({k: v for k, v in env.items() if k != "boundary"}) == []


def test_forbidden_key_in_attributes_is_caught(exporter, entities):
    """If a SEAL-owned key ever reaches the envelope, export must fail loudly."""
    entities.register(
        Entity(entity_id="e.1", entity_type="person", canonical_name="X",
               attributes={"prompt": "generate a task"}),
        ACTOR,
    )
    with pytest.raises(ValidationError) as ei:
        exporter.export(exported_at=STAMP)
    assert "SEAL-owned key" in str(ei.value)


# -- attack: prove the negative scope claims --------------------------------


def test_foundry_declares_no_runtime_ownership_concepts():
    """ADR-0130 forbids the Foundry from owning ledger/authority/verification."""
    banned_defs = (
        "class ProofGraph", "class EvidenceEngine", "class ProofLedger",
        "def append_event", "class CAPTRuntime", "def require_authority",
        "def evaluate_policy", "def issue_grant", "class OutboxDispatcher",
    )
    for path in (REPO / "capt_foundry").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for b in banned_defs:
            assert b not in text, "%s defines runtime-owned concept %r" % (path.name, b)


def test_foundry_has_no_import_time_side_effects():
    """No global singleton, no construction at import (composition-root rule)."""
    code = (
        "import sys, sqlite3;"
        "orig = sqlite3.connect;"
        "sqlite3.connect = lambda *a, **k: (_ for _ in ()).throw("
        "AssertionError('connected at import time'));"
        "import capt_foundry;"
        "sqlite3.connect = orig;"
        "print('clean')"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(REPO))
    assert r.returncode == 0, r.stderr
    assert "clean" in r.stdout


def test_foundry_writes_no_files_at_import():
    code = "\n".join(
        [
            "import builtins",
            "real = builtins.open",
            "def guard(f, mode='r', *a, **k):",
            "    if any(m in str(mode) for m in 'wax'):",
            "        raise AssertionError('wrote %s' % (f,))",
            "    return real(f, mode, *a, **k)",
            "builtins.open = guard",
            "import capt_foundry",
            "builtins.open = real",
            "print('clean')",
        ]
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(REPO))
    assert r.returncode == 0, r.stderr
    assert "clean" in r.stdout


def test_no_submission_or_prompt_generation_capability():
    """Captain constraint: no automatic prompt generation, no submission."""
    banned = ("def submit", "def generate_prompt", "def build_prompt",
              "def send(", "def post(", "def upload")
    for path in (REPO / "capt_foundry").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for b in banned:
            assert b not in text, "%s exposes %r" % (path.name, b)


# -- attack: non-determinism ------------------------------------------------


def test_dict_ordering_cannot_change_a_digest(corpora):
    a = CorpusManifest(corpus_id="c.1", name="x", root_label="r",
                       documents=[Document(document_id="d.1", relative_path="a",
                                           content_digest=digest_bytes(b"a"), byte_size=1)])
    b = CorpusManifest(corpus_id="c.1", name="x", root_label="r",
                       documents=[Document(document_id="d.1", relative_path="a",
                                           content_digest=digest_bytes(b"a"), byte_size=1)])
    assert a.manifest_digest() == b.manifest_digest()


def test_hash_randomization_does_not_affect_digests():
    """PYTHONHASHSEED must not change any digest (subprocess, different seeds)."""
    code = (
        "import sys; sys.path.insert(0, %r);"
        "from capt_foundry.canonical import digest;"
        "print(digest({'z':1,'a':[{'m':2,'b':3}],'k':'v'}))" % str(REPO)
    )
    outs = set()
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)
        assert r.returncode == 0, r.stderr
        outs.add(r.stdout.strip())
    assert len(outs) == 1


def test_publish_rejects_partial_state_on_dangling_reference(publisher, entities):
    """A failed publish must leave NO asset row behind."""
    entities.register(Entity(entity_id="e.1", entity_type="person", canonical_name="X"), ACTOR)
    with pytest.raises(DanglingReference):
        publisher.publish(
            CuratedAsset(asset_id="a.1", name="X", entity_ids=["e.1"], corpus_ids=["c.ghost"]),
            ACTOR, published_at=STAMP,
        )
    assert publisher.get("a.1") is None
