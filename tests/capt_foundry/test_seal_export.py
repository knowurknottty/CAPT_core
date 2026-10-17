"""SEAL export: boundary enforcement, determinism, and one-directional dependency."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from capt_foundry import Entity, EntityAlias
from capt_foundry.canonical import digest_bytes
from capt_foundry.corpus import CorpusManifest, Document
from capt_foundry.errors import UnknownEntity
from capt_foundry.seal_export import (
    FORBIDDEN_KEYS,
    SEAL_EXPORT_FORMAT,
    SealAssetExporter,
    _scan_forbidden,
)

ACTOR = "human:captain"
STAMP = "2026-08-03T00:00:00Z"
REPO = Path(__file__).resolve().parents[2]


@pytest.fixture()
def seeded(entities, aliases, corpora):
    entities.register(
        Entity(entity_id="e.ada", entity_type="person", canonical_name="Ada Lovelace",
               evidence_ids=["ev.1"], attributes={"field": "mathematics"}),
        ACTOR,
    )
    aliases.register(
        EntityAlias(alias_id="a.1", entity_id="e.ada", alias="A. Lovelace",
                    confidence="evidence_backed", evidence_ids=["ev.1"]),
        ACTOR,
    )
    corpora.register(
        CorpusManifest(corpus_id="c.1", name="Notes", root_label="fixtures",
                       documents=[Document(document_id="c.1.d0", relative_path="a.txt",
                                           content_digest=digest_bytes(b"alpha"), byte_size=5)]),
        ACTOR,
    )
    return True


# -- shape ------------------------------------------------------------------


def test_export_shape(exporter, seeded):
    env = exporter.export(exported_at=STAMP)
    assert env["format"] == SEAL_EXPORT_FORMAT
    assert env["format_version"] == "1.0.0"
    assert env["producer"] == "capt_foundry"
    assert env["entities"][0]["entity_id"] == "e.ada"
    assert env["corpora"][0]["corpus_id"] == "c.1"


def test_export_includes_aliases_and_freshness(exporter, seeded):
    env = exporter.export(exported_at=STAMP)
    assert env["entities"][0]["aliases"][0]["alias"] == "A. Lovelace"
    assert env["corpora"][0]["freshness"] == "current"


def test_export_selective(exporter, seeded):
    env = exporter.export(entity_ids=["e.ada"], corpus_ids=[], exported_at=STAMP)
    assert len(env["entities"]) == 1 and env["corpora"] == []


def test_export_unknown_entity_raises(exporter, seeded):
    with pytest.raises(UnknownEntity):
        exporter.export(entity_ids=["e.ghost"])


def test_export_preserves_provenance(exporter, seeded):
    env = exporter.export(exported_at=STAMP)
    assert env["entities"][0]["provenance"]["registered_by"] == ACTOR
    assert env["corpora"][0]["documents"][0]["content_digest"].startswith("sha256:")


# -- boundary ---------------------------------------------------------------


def test_export_declares_ownership_boundary(exporter, seeded):
    b = exporter.export(exported_at=STAMP)["boundary"]
    assert b["evidence_owner"] == "capt_runtime"
    assert b["verification_owner"] == "capt_runtime"
    assert b["ledger_owner"] == "capt_runtime.store"
    assert b["governance_owner"] == "capt_runtime.authority"
    assert b["case_owner"] == "project_seal"


def test_export_emits_no_seal_owned_concepts(exporter, seeded):
    """The Foundry must never author a case, ruleset, prompt, or submission."""
    env = exporter.export(exported_at=STAMP)
    # 'boundary' documents ownership using these words as VALUES, which is fine;
    # the scan is over KEYS.
    assert _scan_forbidden({k: v for k, v in env.items() if k != "boundary"}) == []


def test_forbidden_key_scan_actually_detects(exporter, seeded):
    assert _scan_forbidden({"prompt": "x"}) == ["$.prompt"]
    assert _scan_forbidden({"a": [{"case_id": 1}]}) == ["$.a[0].case_id"]
    assert _scan_forbidden({"safe": 1}) == []


def test_forbidden_key_set_covers_seal_concepts():
    for k in ("case", "ruleset", "candidate", "prompt", "submission", "reviewer",
              "model_run", "final_answer"):
        assert k in FORBIDDEN_KEYS


def test_evidence_exported_as_refs_never_as_verdicts(exporter, seeded):
    env = exporter.export(exported_at=STAMP)
    assert env["entities"][0]["evidence_refs"] == ["ev.1"]
    flat = str(env).lower()
    for banned in ("'verified'", "verificationstatus", "guardverdict", "promotionstate"):
        assert banned not in flat


def test_foundry_does_not_import_seal():
    """One-directional dependency, asserted against the source tree."""
    hits = []
    for path in (REPO / "capt_foundry").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            s = line.strip()
            if s.startswith(("import ", "from ")) and "seal" in s.lower():
                if "seal_export" not in s and "capt_foundry" not in s:
                    hits.append("%s: %s" % (path.name, s))
    assert hits == [], "capt_foundry must not import SEAL: %s" % hits


def test_foundry_makes_no_network_imports():
    """No network access anywhere in the Foundry (Captain constraint)."""
    banned = ("requests", "urllib.request", "httpx", "aiohttp", "socket", "http.client")
    hits = []
    for path in (REPO / "capt_foundry").rglob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith(("import ", "from ")):
                for b in banned:
                    if s.startswith("import %s" % b) or s.startswith("from %s" % b):
                        hits.append("%s: %s" % (path.name, s))
    assert hits == [], "network import in Foundry: %s" % hits


def test_foundry_imports_without_capt_runtime_present():
    """Foundry must not hard-depend on the generated contract bindings."""
    code = (
        "import sys;"
        "sys.modules['capt_runtime']=None;"
        "import capt_foundry;"
        "print(capt_foundry.FOUNDRY_SCHEMA_VERSION)"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(REPO))
    assert r.returncode == 0, r.stderr
    assert "capt-foundry.v1" in r.stdout


# -- integrity --------------------------------------------------------------


def test_export_is_deterministic(exporter, seeded):
    a = exporter.export(exported_at=STAMP)
    b = exporter.export(exported_at=STAMP)
    assert a == b
    assert a["content_digest"] == b["content_digest"]


def test_content_digest_excludes_timestamp(exporter, seeded):
    a = exporter.export(exported_at="2026-08-03T00:00:00Z")
    b = exporter.export(exported_at="2027-01-01T00:00:00Z")
    assert a["content_digest"] == b["content_digest"]


def test_digest_changes_with_content(exporter, seeded, entities):
    a = exporter.export(exported_at=STAMP)
    entities.register(
        Entity(entity_id="e.cb", entity_type="person", canonical_name="Charles Babbage"), ACTOR
    )
    b = exporter.export(exported_at=STAMP)
    assert a["content_digest"] != b["content_digest"]


def test_verify_round_trip(exporter, seeded):
    env = exporter.export(exported_at=STAMP)
    assert SealAssetExporter.verify(env)["matches"] is True


def test_verify_detects_tampering(exporter, seeded):
    env = exporter.export(exported_at=STAMP)
    env["entities"][0]["canonical_name"] = "Tampered"
    assert SealAssetExporter.verify(env)["matches"] is False
