# CAPT Solo v0.1 — Extending

This guide shows how to add future capabilities **without breaking existing
projects**. Every extension point below is a seam in the v0.1 code; the
implementations are intentionally absent.

---

## 1. Vector / semantic search

**Seam:** `capt_solo.memory.search.SearchAdapter`

```python
from capt_solo.memory.search import SearchAdapter, SearchHit

class MyVectorAdapter(SearchAdapter):
    def index(self, memory_id, text, metadata): ...
    def remove(self, memory_id): ...
    def search(self, query, limit=10) -> list[SearchHit]: ...
    def clear(self): ...

from capt_solo.api import MemoryEngine
eng = MemoryEngine()
eng.set_search_adapter(MyVectorAdapter())
```

Public `store` / `search` / `list` signatures are unchanged. Old projects keep
working with the default `KeywordSearchAdapter`.

---

## 2. Distributed KHSB (networking)

**Seam:** `capt_solo.khsb.bus.KHSB` (in-process in v0.1)

Future: implement a `Transport` interface and have `KHSB.publish/request` route
through it when configured. The public method signatures (`publish`, `subscribe`,
`request`, `reply`, `ack`) stay identical, so existing subscribers keep working.

---

## 3. Remote memory stores

**Seam:** `capt_solo.memory.engine.MemoryEngine`

Swap the storage backend behind the same public methods. As long as
`store/get/update/delete/search/list/export/import/backup/restore` keep their
signatures, callers (including the Hermes plugin) are unaffected.

---

## 4. Multi-agent federation

**Seam:** CTP `correlation_id` + `idempotency_key`

Because every transaction carries a correlation id and an idempotency key, a
future coordinator can fan out operations to agents and dedupe by key. The
journal already records correlation ids; no schema change needed for v0.1
compatibility.

---

## 5. bioCAPT integration

**Seam:** `MemoryEngine` as a local memory sink

A future bioCAPT layer can read/write through the public `capt_*` tools or the
`MemoryEngine` API directly. No changes to v0.1 are required to consume it.

---

## Rules for extensions

- **Never change a public signature within a major version.** Add, don't break.
- **Keep the default path dependency-free.** New backends are opt-in.
- **Stay local-first by default.** Networking/remote features must be off unless
  explicitly enabled by the user.
- **Test the seam.** Add a test that plugs a stub adapter/transport and confirms
  the public API behaves identically.
