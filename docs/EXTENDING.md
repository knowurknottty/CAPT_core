# Extending CAPT Solo

**Add capabilities without breaking the stable public surface.**

CAPT Solo is designed around extension seams. New backends and transports should plug in behind supported APIs rather than forcing downstream callers to depend on internal modules.

## Start here

Use this rule first:

> Extend behind `capt_solo.api`; do not make callers import implementation details.

Before adding an extension, decide which seam it belongs to:

| Goal | Extension seam |
|---|---|
| Add semantic or vector search | `SearchAdapter` |
| Add a different memory backend | `MemoryEngine` boundary |
| Add networking or distributed messaging | KHSB transport seam |
| Coordinate multiple agents | CTP correlation and idempotency |
| Add another local consumer | public API or `capt_*` tools |

## Extension contract

Every extension should preserve four properties:

1. **Compatibility** — existing public method signatures continue to work.
2. **Local-first defaults** — remote behavior remains opt-in.
3. **Failure isolation** — an optional component can degrade without taking down the core runtime.
4. **Evidence** — the extension includes tests and a clear verification path.

## Add semantic or vector search

Implement `SearchAdapter`:

```python
from capt_solo.memory.search import SearchAdapter, SearchHit

class MyVectorAdapter(SearchAdapter):
    def index(self, memory_id, text, metadata):
        ...

    def remove(self, memory_id):
        ...

    def search(self, query, limit=10) -> list[SearchHit]:
        ...

    def clear(self):
        ...
```

Then install it through the public memory boundary:

```python
from capt_solo.api import MemoryEngine

engine = MemoryEngine()
engine.set_search_adapter(MyVectorAdapter())
```

Existing `store`, `search`, and `list` callers should continue to work unchanged.

## Add another memory backend

Keep the supported memory behavior stable:

```text
store
get
update
delete
search
list
export
import
backup
restore
integrity_check
```

A remote or alternate local backend should remain hidden behind this contract.

Minimum expectations:

- preserve provenance and confidence fields
- preserve namespace and tag behavior
- define backup and restore semantics
- provide integrity checks
- document consistency and failure behavior
- remain opt-in when network access is involved

## Add a KHSB transport

The current public KHSB runtime is local and in-process. A future transport can route the same public operations through another implementation:

```text
publish
subscribe
request
reply
ack
```

A transport extension should document:

- authentication assumptions
- message ordering
- retry behavior
- duplicate handling
- timeout semantics
- network failure behavior
- whether acknowledgements are durable

Do not describe a transport as implemented until those behaviors are supported and verified.

## Coordinate multiple agents

Use CTP `correlation_id` to group related work and `idempotency_key` to prevent duplicate application.

A coordinator can fan out work while keeping each consequential action transaction-bounded.

Before claiming multi-agent support, verify:

- duplicate requests do not double-apply effects
- partial failures remain discoverable
- receipts identify the responsible actor or component
- recovery can distinguish pending, committed, and aborted work

## Add another local consumer

A local application, model runtime, or research layer should use:

- `capt_solo.api`, or
- the public `capt_*` plugin tools

It should not mutate SQLite tables or append-only journals directly.

## Tests required for an extension

At minimum, add tests that demonstrate:

- the public API still behaves as documented
- the default runtime works without the extension installed
- extension failure does not corrupt core state
- transaction and recovery behavior remain truthful
- unsupported claims are not promoted to verified
- migration or schema changes preserve backup and integrity gates

## Documentation required

For each extension, document:

- current implementation status
- configuration and defaults
- trust assumptions
- failure behavior
- data handling
- network behavior, when applicable
- verification commands
- limitations and non-goals

Reserved seams must be labeled as reserved or experimental rather than implemented.

## Review checklist

Before merging an extension, confirm:

- no supported signature was broken
- remote behavior is opt-in
- secrets are not passed through unsafe boundaries
- rollback or recovery exists for consequential state changes
- tests cover failure as well as success
- evidence supports every public capability claim

## Related documentation

- [API Reference](API.md)
- [Architecture](ARCHITECTURE.md)
- [Security Boundaries](SECURITY.md)
- [Design Rationale](DESIGN.md)
