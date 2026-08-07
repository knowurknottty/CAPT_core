# CAPT Public Integration Reference

CAPT Core exposes two supported public surfaces:

1. `capt_solo.api` for in-process CAPT Solo integrations.
2. The installed `capt harness` CLI for governed runtime lifecycle and bounded execution.

They serve different purposes and should not be treated as interchangeable.

## CAPT Solo API

Use `capt_solo.api` for persistent local memory, CTP transactions, KHSB coordination, and proof-governed domain services.

```python
from capt_solo.api import MemoryEngine, CTPRuntime

memory = MemoryEngine()
record = memory.store(
    "CAPT keeps durable state outside the model.",
    namespace="project",
    provenance="user",
)

ctp = CTPRuntime()
tx_id = ctp.begin(meta={"action": "example"})
ctp.commit(tx_id)
```

Use the public API rather than importing internal modules directly.

### Core CAPT Solo capabilities

| Need | Public entry point |
|---|---|
| Store and search durable local knowledge | `MemoryEngine` |
| Record operational transactions and recovery state | `CTPRuntime` |
| Coordinate local in-process messages | `KHSB` |
| Evaluate evidence and capability state | Foundry and proof APIs |
| Guard unsupported claims | `ClaimGuard` |

### Memory Engine

`MemoryEngine` is SQLite-backed persistent local storage. It supports store, get, update, delete, search, list, import/export, backup/restore, integrity checks, and pluggable search adapters.

It is distinct from the Runtime Memory Governor. The Memory Engine stores durable knowledge; the Runtime Memory Governor controls bounded runtime context and trigger policy.

### CTP Runtime

`CTPRuntime` records operational transaction boundaries, receipts, idempotency, correlation identifiers, and recovery state.

CTP does not own the standalone runtime's authoritative event ledger. EventStore owns that authority.

### KHSB

`KHSB` provides local in-process publish/subscribe and request/reply behavior. It is not durable, cross-process, or distributed.

### Foundry and proof APIs

The public domain APIs include proof evidence, capability lifecycle, ClaimGuard, governed skill lifecycle, workflow proof, Knowledge Bubbles, and governance records.

A generated or importable component is not automatically verified.

## CAPT Runtime Harness

Use the installed harness for governed runtime lifecycle:

```zsh
capt harness start
capt harness health
capt harness capabilities
capt harness stop
```

Inspect the exact installed command surface with:

```zsh
capt harness --help
capt harness command --help
```

The harness owns:

- authenticated RuntimeService access;
- EventStore persistence and replay;
- TaskResolver;
- DriverHost;
- Runtime Memory Governor;
- ContextPack construction and rotation;
- idempotent command handling;
- checkpoint and restart continuity;
- bounded external-driver execution;
- persisted evidence and verification state.

The currently proven Hermes-facing operator action is bounded read-only inspection. General unrestricted repository engineering is not claimed.

## External clients and compatibility layers

Hermes and other callers are external clients. A compatibility skill or adapter may invoke the installed CAPT surface, but it must not reconstruct CAPT behavior or assume runtime authority.

Canonical boundary:

```text
external client -> installed CAPT public surface -> CAPT-owned runtime path
```

Prohibited boundary:

```text
external client -> prompt convention -> reconstructed CAPT behavior
```

The historical Hermes compatibility skill has been moved out of CAPT Core for modernization against the v0.5 harness.

## Reachability classifications

Documentation and release evidence distinguish:

- packaged;
- importable API;
- API-only;
- internal runtime service;
- operator-facing;
- local real-process proven;
- hosted-CI proven;
- deferred;
- unproven.

Do not infer operator availability from package inclusion alone.

## Evidence and release status

See [`release_evidence/v0.5`](../release_evidence/v0.5) for exact wheel identities, test matrices, skip reasons, runtime lifecycle evidence, and requirement-to-evidence mappings.

## Related documentation

- [Project overview](../README.md)
- [Architecture](ARCHITECTURE.md)
- [Runtime and integration guide](PLUGIN_GUIDE.md)
- [Security boundaries](SECURITY.md)
- [Whitepaper](WHITEPAPER.md)
