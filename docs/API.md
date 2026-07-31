# CAPT Solo API Reference

**Use `capt_solo.api` for supported integrations.**

This page starts with the smallest useful example, then expands into the full API surface. The Hermes plugin exposes the same supported boundary as named tools.

## Start here

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

Use `capt_solo.api` rather than importing internal modules directly. Internal implementations may evolve while the public boundary remains stable.

## Choose the capability you need

| Need | Public entry point |
|---|---|
| Store and search durable local memory | `MemoryEngine` |
| Record transactional work and recovery state | `CTPRuntime` |
| Coordinate local in-process messages | `KHSB` |
| Work with proof-governed capabilities and skills | Foundry APIs |
| Call CAPT from Hermes | `capt_solo.plugin` tools |

## Memory Engine

### `MemoryEngine(db_path=None)`

SQLite-backed storage. With no path, it uses the default local CAPT data directory.

```python
from capt_solo.api import MemoryEngine

engine = MemoryEngine()
engine.store(
    "Release candidate requires independent verification.",
    namespace="release",
    tags=["audit"],
    provenance="maintainer",
    confidence=0.95,
)

matches = engine.search("independent verification")
```

| Method | Returns | Notes |
|---|---|---|
| `store(content, *, namespace="default", tags=None, provenance="unknown", confidence=1.0, metadata=None)` | `Memory` | Rejects empty content and confidence outside `[0,1]`. |
| `get(memory_id)` | `Memory \| None` | Returns one record when present. |
| `update(memory_id, *, content=None, namespace=None, tags=None, provenance=None, confidence=None, metadata=None)` | `Memory` | Raises if the ID is missing. |
| `delete(memory_id)` | `bool` | `True` when removed. |
| `search(query, *, limit=10, namespace=None, tags=None)` | `list[Memory]` | Uses the active search adapter. |
| `list(*, namespace=None, tags=None, limit=100)` | `list[Memory]` | Newest first. |
| `export_json(path=None)` | `Path` | Human-readable export. |
| `import_json(path, *, merge=True)` | `int` | Returns the number imported. |
| `backup(path=None)` | `Path` | Creates a self-contained database copy. |
| `restore(path)` | `None` | Replaces the live database from backup. |
| `integrity_check()` | `bool` | SQLite integrity plus referential checks. |
| `set_search_adapter(adapter)` | `None` | Replaces the search backend. |
| `close()` | `None` | Commits and closes the connection. |

### `Memory`

Fields:

`memory_id, content, namespace, tags, provenance, confidence, metadata, created_at, updated_at`

Method: `to_dict()`.

### `SearchAdapter`

Interface:

```python
index(memory_id, text, metadata)
remove(memory_id)
search(query, limit=10) -> list[SearchHit]
clear()
```

The default `KeywordSearchAdapter` is deterministic and dependency-free.

## CTP Runtime

### `CTPRuntime(journal_dir=None)`

Append-only transactional execution with receipts and recovery.

```python
from capt_solo.api import CTPRuntime

ctp = CTPRuntime()
tx_id = ctp.begin(
    correlation_id="release-2026-07",
    idempotency_key="publish-candidate-1",
)

if ctp.validate(tx_id, {"tests_passed": True}):
    receipt = ctp.commit(tx_id)
else:
    receipt = ctp.abort(tx_id)
```

| Method | Returns | Notes |
|---|---|---|
| `begin(correlation_id=None, idempotency_key=None, meta=None)` | `str` | Raises when a finalized idempotency key is reused. |
| `validate(tx_id, checks)` | `bool` | Records validation in the journal. |
| `commit(tx_id)` | `Receipt` | Finalizes a successful transaction. |
| `abort(tx_id)` | `Receipt` | Finalizes an aborted transaction while preserving history. |
| `note(tx_id, note)` | `None` | Adds an audit note. |
| `get_receipt(tx_id)` | `Receipt \| None` | Returns a finalized receipt. |
| `audit_trail(tx_id)` | `list[dict]` | Returns all events for a transaction. |
| `recover()` | `list[str]` | Returns unfinished transaction IDs. |
| `integrity_check()` | `bool` | Verifies journal integrity. |

### `Receipt`

Fields:

`tx_id, status, correlation_id, idempotency_key, committed_at, events`

Method: `to_dict()`.

## KHSB Message Bus

### `KHSB()`

Local, in-process coordination with publish/subscribe and request/reply behavior.

| Method | Returns | Notes |
|---|---|---|
| `publish(topic, payload, correlation_id=None)` | `str` | Returns a message ID. |
| `subscribe(topic, handler)` | `str` | Registers `handler(Message)`. |
| `unsubscribe(subscription_id)` | `bool` | Removes a subscription. |
| `request(topic, payload, *, timeout=5.0)` | `Any` | Raises `BusError` on timeout. |
| `reply(request_message, payload)` | `str` | Replies to a request message. |
| `ack(message_id)` | `None` | Marks a message acknowledged. |
| `is_acked(message_id)` | `bool` | Checks acknowledgement state. |
| `pending_messages(topic=None)` | `list[dict]` | Lists pending messages. |
| `reset()` | `None` | Clears in-process state. |

### `Message`

Fields:

`message_id, topic, payload, correlation_id, reply_to, ts, type`

Method: `to_dict()`.

## Hermes Plugin Tools

The Hermes plugin exposes supported CAPT operations as named tools. Common examples:

| Tool | Maps to |
|---|---|
| `capt_store_memory` | `MemoryEngine.store` |
| `capt_search_memory` | `MemoryEngine.search` |
| `capt_get_memory` | `MemoryEngine.get` |
| `capt_begin_transaction` | `CTPRuntime.begin` |
| `capt_commit_transaction` | `CTPRuntime.commit` |
| `capt_abort_transaction` | `CTPRuntime.abort` |
| `capt_send_message` | `KHSB.publish` |
| `capt_health` | runtime health |
| `capt_export_project` | `MemoryEngine.export_json` |
| `capt_import_project` | `MemoryEngine.import_json` |

Plugin calls return a dictionary with an `ok` boolean. Error paths return an error object rather than raising into Hermes.

See [Plugin Guide](PLUGIN_GUIDE.md) for the full public tool inventory.

## Foundry APIs

Foundry adds evidence, capability lifecycles, ClaimGuard, governed skills, workflows, and Knowledge Bubbles.

### `ProofEngine(conn)`

Records evidence and evaluates it against requirements.

| Method | Purpose |
|---|---|
| `record(...)` | Store one evidence object. |
| `get(evidence_id)` | Retrieve evidence. |
| `aggregate(capability_id)` | Evaluate requirement satisfaction. |
| `set_requirements(scope, requirements)` | Replace requirements for a scope. |
| `get_requirements(scope)` | Read requirements for a scope. |

### `CapabilityRegistry(conn, proof)`

Tracks capability state and degradation.

Primary lifecycle:

```text
candidate -> validated -> proven -> verified
```

Additional states include experimental, degraded, deprecated, and revoked.

Important methods:

- `register(...)`
- `verify(...)`
- `mark_proven(...)`
- `govern_approve(...)`
- `degrade(...)`
- `get_degradations(...)`
- `get(...)`

### `SkillFoundry(conn, proof, procedure_store)`

Moves generated skills through validation, review, approval, publication, deprecation, and revocation.

Important methods:

- `create_candidate(...)`
- `build_skill(...)`
- `validate(...)`
- `submit_for_review(...)`
- `approve(...)`
- `publish(...)`
- `deprecate(...)`
- `revoke(...)`

### `ClaimGuard(registry, proof)`

```python
verdict = claim_guard.verify_claim(
    "The release is verified.",
    capability_id="release-verification",
)
```

Returns a `ClaimVerdict` containing support status, lifecycle state, and governed language. Unsupported claims are downgraded rather than presented as verified.

### `WorkflowProofEngine(conn, foundry, proof)`

Evaluates composed workflows independently of their component verification.

Important methods:

- `evaluate(...)`
- `record_evidence(...)`
- `validate()`

### `KnowledgeBubbleRuntime(conn, foundry)`

Builds, imports, validates, approves, installs, and exports governed packages.

Imported bubbles are quarantined by default.

Important methods:

- `build_bubble(...)`
- `import_bubble(...)`
- `validate_bubble(...)`
- `approve_bubble(...)`
- `install_bubble(...)`

### `Governance(conn, ctp, *, foundry, registry, bubbles)`

Wraps consequential actions in CTP transactions and audit records.

### `SkillCurator(foundry)`

Detects duplicate, overlapping, unsafe, incomplete, or obsolete skill definitions and returns recommendations.

## Errors

Public errors derive from `CaptSoloError`:

- `MemoryError_`
- `TransactionError`
- `IdempotencyError`
- `BusError`
- `IntegrityError`
- `ConfigurationError`
- `MigrationBackupError`

## Related documentation

- [Quickstart and project overview](../README.md)
- [Architecture](ARCHITECTURE.md)
- [Plugin Guide](PLUGIN_GUIDE.md)
- [Skill Guide](SKILL_GUIDE.md)
- [Extending CAPT](EXTENDING.md)
