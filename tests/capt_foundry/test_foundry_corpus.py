"""Corpus manifest, duplicate detection, freshness, and path-escape refusal."""

from __future__ import annotations

import os

import pytest

from capt_foundry.canonical import digest_bytes
from capt_foundry.corpus import CorpusManifest, Document, index_directory
from capt_foundry.errors import DuplicateIdentity, PathEscape, UnknownEntity, ValidationError

ACTOR = "human:captain"
D1 = digest_bytes(b"alpha")
D2 = digest_bytes(b"beta")


def _doc(i, path, dg=D1, size=5):
    return Document(document_id="c.1.d%d" % i, relative_path=path, content_digest=dg, byte_size=size)


def _manifest(docs=None):
    return CorpusManifest(
        corpus_id="c.1", name="Test corpus", root_label="fixtures",
        documents=docs if docs is not None else [_doc(0, "a.txt"), _doc(1, "b.txt", D2)],
    )


# -- validation -------------------------------------------------------------


def test_document_rejects_bad_digest():
    with pytest.raises(ValidationError):
        Document(document_id="d.1", relative_path="a", content_digest="nope", byte_size=1)


def test_document_rejects_negative_size():
    with pytest.raises(ValidationError):
        Document(document_id="d.1", relative_path="a", content_digest=D1, byte_size=-1)


def test_manifest_rejects_duplicate_paths():
    with pytest.raises(ValidationError):
        CorpusManifest(
            corpus_id="c.1", name="x", root_label="r",
            documents=[_doc(0, "same.txt"), _doc(1, "same.txt")],
        )


def test_manifest_rejects_duplicate_ids():
    d = _doc(0, "a.txt")
    with pytest.raises(ValidationError):
        CorpusManifest(corpus_id="c.1", name="x", root_label="r", documents=[d, d])


# -- digest determinism -----------------------------------------------------


def test_manifest_digest_is_order_independent():
    a = CorpusManifest(corpus_id="c.1", name="x", root_label="r",
                       documents=[_doc(0, "a.txt"), _doc(1, "b.txt", D2)])
    b = CorpusManifest(corpus_id="c.1", name="x", root_label="r",
                       documents=[_doc(1, "b.txt", D2), _doc(0, "a.txt")])
    assert a.manifest_digest() == b.manifest_digest()


def test_manifest_digest_changes_with_membership():
    base = _manifest()
    more = CorpusManifest(
        corpus_id="c.1", name="Test corpus", root_label="fixtures",
        documents=list(base.documents) + [_doc(2, "c.txt", D2)],
    )
    assert base.manifest_digest() != more.manifest_digest()


def test_manifest_digest_changes_with_content():
    a = CorpusManifest(corpus_id="c.1", name="x", root_label="r", documents=[_doc(0, "a.txt", D1)])
    b = CorpusManifest(corpus_id="c.1", name="x", root_label="r", documents=[_doc(0, "a.txt", D2)])
    assert a.manifest_digest() != b.manifest_digest()


def test_duplicate_groups_detects_same_content():
    m = CorpusManifest(
        corpus_id="c.1", name="x", root_label="r",
        documents=[_doc(0, "a.txt", D1), _doc(1, "copy.txt", D1), _doc(2, "c.txt", D2)],
    )
    assert m.duplicate_groups() == {D1: ["c.1.d0", "c.1.d1"]}


# -- registry ---------------------------------------------------------------


def test_register_and_read_back(corpora):
    corpora.register(_manifest(), ACTOR)
    row = corpora.require("c.1")
    assert row["document_count"] == 2
    assert row["status"] == "current"
    assert len(corpora.documents("c.1")) == 2


def test_register_idempotent(corpora):
    corpora.register(_manifest(), ACTOR)
    corpora.register(_manifest(), ACTOR)
    assert corpora.require("c.1")["document_count"] == 2


def test_register_conflicting_manifest_refused(corpora):
    corpora.register(_manifest(), ACTOR)
    with pytest.raises(DuplicateIdentity):
        corpora.register(_manifest([_doc(0, "different.txt")]), ACTOR)


def test_unknown_corpus_raises(corpora):
    with pytest.raises(UnknownEntity):
        corpora.require("c.nope")


def test_cross_corpus_duplicate_detection(corpora):
    corpora.register(_manifest(), ACTOR)
    corpora.register(
        CorpusManifest(corpus_id="c.2", name="Other", root_label="r",
                       documents=[Document(document_id="c.2.d0", relative_path="dup.txt",
                                           content_digest=D1, byte_size=5)]),
        ACTOR,
    )
    hits = corpora.find_by_content_digest(D1)
    assert {h["corpus_id"] for h in hits} == {"c.1", "c.2"}


def test_freshness_transitions(corpora):
    corpora.register(_manifest(), ACTOR)
    corpora.mark_stale("c.1")
    assert corpora.require("c.1")["status"] == "stale"
    corpora.mark_current("c.1")
    assert corpora.require("c.1")["status"] == "current"


def test_verify_against_manifest_reports_drift(corpora):
    corpora.register(_manifest(), ACTOR)
    changed = _manifest([_doc(0, "a.txt", D2), _doc(1, "b.txt", D2)])
    report = corpora.verify_against_manifest(changed)
    assert report["matches"] is False
    assert report["changed"] == ["c.1.d0"]

    added = _manifest([_doc(0, "a.txt"), _doc(1, "b.txt", D2), _doc(2, "new.txt", D2)])
    r2 = corpora.verify_against_manifest(added)
    assert r2["added"] == ["c.1.d2"] and r2["removed"] == []


def test_verify_matches_when_unchanged(corpora):
    corpora.register(_manifest(), ACTOR)
    assert corpora.verify_against_manifest(_manifest())["matches"] is True


# -- indexing safety --------------------------------------------------------


def test_index_directory_digests_real_files(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"alpha")
    (tmp_path / "b.txt").write_bytes(b"beta")
    m = index_directory("c.1", "Test", tmp_path, relative_paths=["a.txt", "b.txt"])
    assert len(m.documents) == 2
    by_path = {d.relative_path: d for d in m.documents}
    assert by_path["a.txt"].content_digest == digest_bytes(b"alpha")
    assert by_path["a.txt"].byte_size == 5


def test_index_directory_is_deterministic(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"alpha")
    m1 = index_directory("c.1", "T", tmp_path, relative_paths=["a.txt"])
    m2 = index_directory("c.1", "T", tmp_path, relative_paths=["a.txt"])
    assert m1.manifest_digest() == m2.manifest_digest()


def test_index_refuses_traversal(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (tmp_path / "secret.txt").write_bytes(b"secret")
    with pytest.raises(PathEscape):
        index_directory("c.1", "T", root, relative_paths=["../secret.txt"])


def test_index_refuses_absolute_path(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(PathEscape):
        index_directory("c.1", "T", root, relative_paths=["/etc/hosts"])


def test_index_refuses_symlink_escape(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside")
    link = root / "link.txt"
    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError):  # pragma: no cover
        pytest.skip("symlinks unavailable")
    with pytest.raises(PathEscape):
        index_directory("c.1", "T", root, relative_paths=["link.txt"])


def test_index_refuses_symlinked_parent_dir(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "f.txt").write_bytes(b"x")
    try:
        os.symlink(outside, root / "sub")
    except (OSError, NotImplementedError):  # pragma: no cover
        pytest.skip("symlinks unavailable")
    with pytest.raises(PathEscape):
        index_directory("c.1", "T", root, relative_paths=["sub/f.txt"])


def test_index_refuses_missing_file(tmp_path):
    with pytest.raises(ValidationError):
        index_directory("c.1", "T", tmp_path, relative_paths=["nope.txt"])


def test_index_refuses_non_directory_root(tmp_path):
    f = tmp_path / "file.txt"
    f.write_bytes(b"x")
    with pytest.raises(ValidationError):
        index_directory("c.1", "T", f, relative_paths=[])


def test_index_never_recurses_implicitly(tmp_path):
    """No broad scan: only the explicitly named paths are indexed."""
    (tmp_path / "named.txt").write_bytes(b"a")
    (tmp_path / "unnamed.txt").write_bytes(b"b")
    sub = tmp_path / "deep"
    sub.mkdir()
    (sub / "hidden.txt").write_bytes(b"c")
    m = index_directory("c.1", "T", tmp_path, relative_paths=["named.txt"])
    assert [d.relative_path for d in m.documents] == ["named.txt"]
