# CAPT Public Integration Reference

> Generated from the installed v0.5 wheel by introspecting the public surface.
> Signatures below are **real signatures read from source** — not hand-maintained copies.
> Regenerate with `scripts/generate_api_reference.py` and validate with
> `python3 -m pytest tests/test_api_reference.py -q`. Do not edit by hand.
> Source of truth: the installed `capt_solo` package at the referenced commit.

CAPT Core exposes two supported public surfaces:

1. `capt_solo.api` for in-process CAPT Solo integrations (memory, CTP, KHSB, proof-governed services).
2. The installed `capt harness` CLI for governed runtime lifecycle and bounded execution.

They serve different purposes and are not interchangeable.

---

## 1. `capt_solo.api` public surface

```text
BusError, CTPRuntime, CaptSoloError, ConfigurationError, DisabledSemanticAdapter, IdempotencyError, IntegrityError, KHSB, LifecycleEngine, LifecycleManager, LifecycleState, Memory, MemoryEngine, MemoryError_, MemoryTier, Message, Procedure, ProcedureStore, ProspectiveIntent, ProspectiveStore, Receipt, RestartPacket, RetrievalFeedback, SearchAdapter, SearchHit, SemanticAdapter, SessionRuntime, TransactionError, annotations, antitoken, backup_dir, context, csg, ctp_journal_dir, data_dir, get_adapter, health, home_dir, khsb_dir, memory_db_path, models, pipeline, register_adapter, trust
```

---

## 2. Core class method signatures (read from source)

### `MemoryEngine`

Local-first memory store backed by SQLite.

| Method | Signature |
|---|---|
| `add_alias` | `(alias: 'str', memory_id: 'str') -> 'None'` |
| `add_relation` | `(source: 'str', target: 'str', edge_type: 'str', *, weight: 'float' = 1.0, confidence: 'float' = 1.0, provenance: 'str' = 'unknown', ctp_tx_id: 'Optional[str]' = None) -> 'str'` |
| `backup` | `(path: 'Optional[Path]' = None) -> 'Path'` |
| `close` | `() -> 'None'` |
| `delete` | `(memory_id: 'str') -> 'bool'` |
| `detect_conflicts` | `(memory_id: 'str') -> 'List[Dict[str, Any]]'` |
| `export_json` | `(path: 'Optional[Path]' = None) -> 'Path'` |
| `find_duplicates` | `(content: 'str', *, namespace: 'str' = 'default', tags: 'Optional[List[str]]' = None) -> 'List[Dict[str, Any]]'` |
| `find_path` | `(source: 'str', target: 'str', max_depth: 'int' = 6)` |
| `get` | `(memory_id: 'str') -> 'Optional[Memory]'` |
| `get_neighbors` | `(memory_id: 'str')` |
| `import_json` | `(path: 'Path', *, merge: 'bool' = True) -> 'int'` |
| `integrity_check` | `() -> 'bool'` |
| `list` | `(*, namespace: 'Optional[str]' = None, tags: 'Optional[List[str]]' = None, limit: 'int' = 100) -> 'List[Memory]'` |
| `list_conflicts` | `(*, unresolved_only: 'bool' = True) -> 'List[Dict[str, Any]]'` |
| `mark_superseded` | `(memory_id: 'str', *, by: 'Optional[str]' = None, ctp_tx_id: 'Optional[str]' = None) -> 'bool'` |
| `merge` | `(source_id: 'str', target_id: 'str', *, ctp_tx_id: 'Optional[str]' = None) -> 'bool'` |
| `record_conflict` | `(a: 'str', b: 'str', *, reason: 'Optional[str]' = None, ctp_tx_id: 'Optional[str]' = None) -> 'str'` |
| `remove_relation` | `(edge_id: 'str') -> 'bool'` |
| `resolve_alias` | `(alias: 'str') -> 'Optional[str]'` |
| `resolve_conflict` | `(conflict_id: 'str') -> 'bool'` |
| `restore` | `(path: 'Path') -> 'None'` |
| `search` | `(query: 'str', *, limit: 'int' = 10, namespace: 'Optional[str]' = None, tags: 'Optional[List[str]]' = None) -> 'List[Memory]'` |
| `set_search_adapter` | `(adapter: 'SearchAdapter') -> 'None'` |
| `store` | `(content: 'str', *, namespace: 'str' = 'default', tags: 'Optional[List[str]]' = None, provenance: 'str' = 'unknown', confidence: 'float' = 1.0, metadata: 'Optional[Dict[str, Any]]' = None, tier: 'str' = 'durable', lifecycle_state: 'str' = 'active') -> 'Memory'` |
| `update` | `(memory_id: 'str', *, content: 'Optional[str]' = None, namespace: 'Optional[str]' = None, tags: 'Optional[List[str]]' = None, provenance: 'Optional[str]' = None, confidence: 'Optional[float]' = None, metadata: 'Optional[Dict[str, Any]]' = None, tier: 'Optional[str]' = None, lifecycle_state: 'Optional[str]' = None) -> 'Memory'` |

### `CTPRuntime`

Small append-only local transaction journal.

| Method | Signature |
|---|---|
| `abort` | `(tx_id: 'str') -> 'Receipt'` |
| `audit_trail` | `(tx_id: 'str') -> 'List[Dict[str, Any]]'` |
| `begin` | `(correlation_id: 'Optional[str]' = None, idempotency_key: 'Optional[str]' = None, meta: 'Optional[Dict[str, Any]]' = None) -> 'str'` |
| `close` | `() -> 'None'` |
| `commit` | `(tx_id: 'str') -> 'Receipt'` |
| `get_receipt` | `(tx_id: 'str') -> 'Receipt'` |
| `integrity_check` | `() -> 'bool'` |
| `note` | `(tx_id: 'str', note: 'str') -> 'None'` |
| `receipts` | `() -> 'List[Receipt]'` |
| `recover` | `() -> 'List[str]'` |
| `validate` | `(tx_id: 'str', result: 'Any') -> 'bool'` |

### `KHSB`

In-process publish/subscribe/request-reply bus.

| Method | Signature |
|---|---|
| `ack` | `(message_id: 'str') -> 'None'` |
| `is_acked` | `(message_id: 'str') -> 'bool'` |
| `pending_messages` | `(topic: 'Optional[str]' = None) -> 'List[Dict[str, Any]]'` |
| `publish` | `(topic: 'str', payload: 'Any', correlation_id: 'Optional[str]' = None) -> 'str'` |
| `reply` | `(request_message: 'Message', payload: 'Any') -> 'str'` |
| `request` | `(topic: 'str', payload: 'Any', *, timeout: 'float' = 5.0) -> 'Any'` |
| `reset` | `() -> 'None'` |
| `subscribe` | `(topic: 'str', handler: 'Handler') -> 'str'` |
| `unsubscribe` | `(subscription_id: 'str') -> 'bool'` |

---

## 3. Foundry public surface (import from `capt_solo.foundry`)

These proof-governed classes are NOT re-exported on `capt_solo.api` at top level.
Import them from `capt_solo.foundry`.

| Class | Public methods |
|---|---|
| `ATEManifest` | 2 |
| `AntiTokenExtractionComponent` | 8 |
| `BubbleValidationReport` | 1 |
| `Capability` | 2 |
| `CapabilityRegistry` | 13 |
| `ClaimGuard` | 2 |
| `ClaimVerdict` | 1 |
| `ColumnDecodeError` | 0 |
| `ComponentUnavailable` | 0 |
| `CompositeWorkflow` | 1 |
| `CompositionEngine` | 2 |
| `CompositionStep` | 1 |
| `CurationFinding` | 1 |
| `Evidence` | 4 |
| `Governance` | 4 |
| `GovernanceReceipt` | 1 |
| `KnowledgeBubbleRuntime` | 8 |
| `ProofAggregate` | 1 |
| `ProofEngine` | 10 |
| `ProofRequirement` | 1 |
| `Skill` | 3 |
| `SkillCurator` | 2 |
| `SkillFoundry` | 14 |
| `StageResult` | 1 |
| `UnsafeConfiguration` | 0 |
| `ValidationHarness` | 1 |
| `ValidationReport` | 1 |
| `WorkflowProof` | 2 |
| `WorkflowProofEngine` | 5 |

---

## 4. Validation

This reference is generated from the installed wheel at the referenced commit. To reproduce:

```
python3 scripts/generate_api_reference.py
python3 -m pytest tests/test_api_reference.py -q
```

The generator introspects `capt_solo.api` and `capt_solo.foundry` and overwrites `docs/API.md`.
The validator asserts the committed `docs/API.md` equals the freshly generated output, so a
drift between code and documentation fails CI rather than silently going stale.

