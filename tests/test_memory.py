"""Tests for the Memory Engine public surface."""

import json
import pytest

from capt_solo.memory.engine import MemoryEngine
from capt_solo.memory.search import KeywordSearchAdapter, SearchHit
from capt_solo.core.errors import MemoryError_, IntegrityError


def test_store_and_get(mem_engine):
    m = mem_engine.store("hello world", namespace="ns1", tags=["a", "b"],
                         provenance="test", confidence=0.7, metadata={"x": 1})
    assert m.memory_id
    assert m.content == "hello world"
    assert m.namespace == "ns1"
    assert m.tags == ["a", "b"]
    assert m.confidence == 0.7
    assert m.metadata == {"x": 1}
    got = mem_engine.get(m.memory_id)
    assert got.content == "hello world"
    assert got.created_at <= got.updated_at


def test_store_empty_content_raises(mem_engine):
    with pytest.raises(MemoryError_):
        mem_engine.store("")


def test_store_bad_confidence_raises(mem_engine):
    with pytest.raises(MemoryError_):
        mem_engine.store("x", confidence=1.5)
    with pytest.raises(MemoryError_):
        mem_engine.store("x", confidence=-0.1)


def test_update_fields(mem_engine):
    m = mem_engine.store("orig", tags=["t1"])
    upd = mem_engine.update(m.memory_id, content="new", confidence=0.3, tags=["t2"])
    assert upd.content == "new"
    assert upd.confidence == 0.3
    assert upd.tags == ["t2"]


def test_update_missing_raises(mem_engine):
    with pytest.raises(MemoryError_):
        mem_engine.update("nope", content="x")


def test_delete(mem_engine):
    m = mem_engine.store("del")
    assert mem_engine.delete(m.memory_id) is True
    assert mem_engine.get(m.memory_id) is None
    assert mem_engine.delete(m.memory_id) is False


def test_search_basic(mem_engine):
    mem_engine.store("alpha beta", tags=["cat"])
    mem_engine.store("gamma delta")
    hits = mem_engine.search("alpha")
    assert len(hits) >= 1
    assert hits[0].content == "alpha beta"


def test_search_namespace_filter(mem_engine):
    mem_engine.store("same text", namespace="A")
    mem_engine.store("same text", namespace="B")
    hits = mem_engine.search("same text", namespace="A")
    assert all(h.namespace == "A" for h in hits)


def test_search_tag_filter(mem_engine):
    mem_engine.store("tagged content", tags=["keep"])
    mem_engine.store("tagged content", tags=["drop"])
    hits = mem_engine.search("tagged", tags=["keep"])
    assert all("keep" in h.tags for h in hits)


def test_list_namespace_and_tags(mem_engine):
    mem_engine.store("one", namespace="proj", tags=["x"])
    mem_engine.store("two", namespace="proj", tags=["y"])
    mem_engine.store("three", namespace="other")
    lst = mem_engine.list(namespace="proj")
    assert len(lst) == 2
    lst2 = mem_engine.list(tags=["x"])
    assert len(lst2) == 1


def test_export_import_roundtrip(mem_engine, tmp_path):
    m = mem_engine.store("export me", namespace="exp", tags=["e"], metadata={"k": "v"})
    p = mem_engine.export_json(tmp_path / "exp.json")
    assert p.exists()
    data = json.loads(p.read_text())
    assert data["format"] == "capt-solo-memory"
    # import into a fresh engine
    eng2 = MemoryEngine(tmp_path / "fresh.db")
    try:
        n = eng2.import_json(p, merge=True)
        assert n >= 1
        got = eng2.get(m.memory_id)
        assert got is not None
        assert got.content == "export me"
    finally:
        eng2.close()


def test_import_missing_file_raises(mem_engine, tmp_path):
    with pytest.raises(MemoryError_):
        mem_engine.import_json(tmp_path / "nope.json")


def test_import_bad_format_raises(mem_engine, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"format": "wrong"}))
    with pytest.raises(MemoryError_):
        mem_engine.import_json(bad)


def test_backup_and_restore(mem_engine, tmp_path):
    m = mem_engine.store("backup this")
    bk = mem_engine.backup(tmp_path / "bk.db")
    assert bk.exists()
    # mutate then restore
    mem_engine.delete(m.memory_id)
    assert mem_engine.get(m.memory_id) is None
    mem_engine.restore(bk)
    assert mem_engine.get(m.memory_id) is not None


def test_restore_missing_raises(mem_engine, tmp_path):
    with pytest.raises(MemoryError_):
        mem_engine.restore(tmp_path / "nope.db")


def test_integrity_check(mem_engine):
    mem_engine.store("ok")
    assert mem_engine.integrity_check() is True


def test_set_search_adapter(mem_engine):
    adapter = KeywordSearchAdapter()
    mem_engine.set_search_adapter(adapter)
    m = mem_engine.store("adapter test")
    hits = mem_engine.search("adapter")
    assert any(h.memory_id == m.memory_id for h in hits)


def test_search_hit_dataclass():
    h = SearchHit(memory_id="m1", score=0.5, snippet="s")
    assert h.memory_id == "m1"
    assert h.score == 0.5


def test_keyword_adapter_empty_query():
    a = KeywordSearchAdapter()
    a.index("m1", "hello world", {"tags": [], "namespace": "d"})
    assert a.search("") == []


def test_keyword_adapter_remove():
    a = KeywordSearchAdapter()
    a.index("m1", "hello", {})
    a.remove("m1")
    assert a.search("hello") == []


def test_keyword_adapter_clear():
    a = KeywordSearchAdapter()
    a.index("m1", "hello", {})
    a.clear()
    assert a.search("hello") == []
