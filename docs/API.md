# CAPT Solo v0.1 — API Reference

All public APIs are reachable through `capt_solo.api`. The Hermes plugin
(`capt_solo.plugin`) exposes the same surface as named tools.

---

## Memory Engine

### `MemoryEngine(db_path=None)`
SQLite-backed store. One instance per file; create with no args to use the
default `~/.capt-solo/data/memory.db`.

| Method | Returns | Notes |
|--------|---------|-------|
| `store(content, *, namespace="default", tags=None, provenance="unknown", confidence=1.0, metadata=None)` | `Memory` | Raises `MemoryError_` on empty content or confidence outside `[0,1]`. |
| `get(memory_id)` | `Memory \| None` | |
| `update(memory_id, *, content=None, namespace=None, tags=None, provenance=None, confidence=None, metadata=None)` | `Memory` | Raises if id missing. |
| `delete(memory_id)` | `bool` | `True` if removed. |
| `search(query, *, limit=10, namespace=None, tags=None)` | `list[Memory]` | Uses the active `SearchAdapter`. |
| `list(*, namespace=None, tags=None, limit=100)` | `list[Memory]` | Newest first. |
| `export_json(path=None)` | `Path` | Human-readable JSON. |
| `import_json(path, *, merge=True)` | `int` | Returns count imported. |
| `backup(path=None)` | `Path` | Self-contained copy of the DB. |
| `restore(path)` | `None` | Overwrites live DB from backup. |
| `integrity_check()` | `bool` | `PRAGMA integrity_check` + tag FK check. |
| `set_search_adapter(adapter)` | `None` | Swap search backend. |
| `close()` | `None` | Commit + close connection. |

### `Memory` dataclass
Fields: `memory_id, content, namespace, tags, provenance, confidence,
metadata, created_at, updated_at`. Method: `to_dict()`.

### `SearchAdapter` (interface)
`index(memory_id, text, metadata)`, `remove(memory_id)`,
`search(query, limit=10) -> list[SearchHit]`, `clear()`.
Default: `KeywordSearchAdapter` (dependency-free, deterministic token overlap).

---

## CTP Runtime

### `CTPRuntime(journal_dir=None)`
Append-only transaction journal.

| Method | Returns | Notes |
|--------|---------|-------|
| `begin(correlation_id=None, idempotency_key=None, meta=None)` | `str` (tx_id) | Raises `IdempotencyError` if key already finalized. |
| `validate(tx_id, checks)` | `bool` | Records validation result in audit trail. |
| `commit(tx_id)` | `Receipt` | Raises `TransactionError` if unknown/already finalized. |
| `abort(tx_id)` | `Receipt` | Rollback marker (history preserved). |
| `note(tx_id, note)` | `None` | Free-form audit note. |
| `get_receipt(tx_id)` | `Receipt \| None` | |
| `audit_trail(tx_id)` | `list[dict]` | All events for the tx. |
| `recover()` | `list[str]` | Replays journal; returns pending tx ids. |
| `integrity_check()` | `bool` | |

### `Receipt` dataclass
Fields: `tx_id, status, correlation_id, idempotency_key, committed_at, events`.
Method: `to_dict()`.

---

## KHSB Message Bus

### `KHSB()`
In-process, networking-free bus.

| Method | Returns | Notes |
|--------|---------|-------|
| `publish(topic, payload, correlation_id=None)` | `str` (message_id) | |
| `subscribe(topic, handler)` | `str` (subscription_id) | `handler(Message)` |
| `unsubscribe(subscription_id)` | `bool` | |
| `request(topic, payload, *, timeout=5.0)` | `Any` | Raises `BusError` on timeout. |
| `reply(request_message, payload)` | `str` | Raises if message is not a request. |
| `ack(message_id)` | `None` | |
| `is_acked(message_id)` | `bool` | |
| `pending_messages(topic=None)` | `list[dict]` | |
| `reset()` | `None` | Clears all state. |

### `Message` dataclass
Fields: `message_id, topic, payload, correlation_id, reply_to, ts, type`.
Method: `to_dict()`.

---

## Hermes Plugin Tools

| Tool | Maps to |
|------|----------|
| `capt_store_memory` | `MemoryEngine.store` |
| `capt_search_memory` | `MemoryEngine.search` |
| `capt_get_memory` | `MemoryEngine.get` |
| `capt_begin_transaction` | `CTPRuntime.begin` |
| `capt_commit_transaction` | `CTPRuntime.commit` |
| `capt_abort_transaction` | `CTPRuntime.abort` |
| `capt_send_message` | `KHSB.publish` |
| `capt_health` | `capt_solo.api.health` |
| `capt_export_project` | `MemoryEngine.export_json` |
| `capt_import_project` | `MemoryEngine.import_json` |

All tools return a `dict` with an `ok` boolean. Error paths return
`{"ok": False, "error": "..."}` rather than raising into Hermes.

---

## v0.4 — Foundry API

All v0.4 classes are importable from `capt_solo.foundry`. The Hermes plugin
exposes them as 10 additional tools (see PLUGIN_GUIDE.md).

### `ProofEngine(conn)`
| Method | Returns | Notes |
|--------|---------|-------|
| `record(type, producer, text_or_hash, trust, *, scope, provenance=None, expiration=None)` | `Evidence` | Records one evidence object. |
| `get(evidence_id)` | `Evidence \| None` | |
| `aggregate(capability_id)` | `ProofAggregate` | `satisfied`, `satisfied_requirements`, `unsatisfied_requirements`, `evidence_count`. |
| `set_requirements(scope, requirements)` | `None` | Replaces requirements for scope. |
| `get_requirements(scope)` | `list[ProofRequirement]` | |

### `CapabilityRegistry(conn, proof)`
| Method | Returns | Notes |
|--------|---------|-------|
| `register(capability_id, name, namespace)` | `None` | Lifecycle → candidate. |
| `verify(capability_id, proof, requirements)` | `dict` | Promotes candidate → validated if aggregate satisfied. Idempotent. |
| `mark_proven(capability_id)` | `None` | validated → proven. |
| `govern_approve(capability_id, *, approver)` | `None` | proven → verified. |
| `degrade(capability_id, reason, *, affected_scope, triggering_evidence="", actor="system", remediation="", ctp_tx_id=None)` | `None` | Records structured degradation; security_revoked → revoked, else → degraded. |
| `get_degradations(capability_id)` | `list[dict]` | All degradation records. |
| `get(capability_id)` | `Capability \| None` | |

### `SkillFoundry(conn, proof, procedure_store)`
| Method | Returns | Notes |
|--------|---------|-------|
| `create_candidate(procedure_id)` | `str` | candidate. |
| `build_skill(candidate_id, *, name, trigger="", purpose="", permissions=None, compatibility="", verification_requirements=None, rollback_strategy=None)` | `str` | generated. |
| `validate(skill_id, harness)` | `ValidationReport` | validating → validated (or stays validating on failure). |
| `submit_for_review(skill_id)` | `None` | validated → reviewing. |
| `approve(skill_id, *, reviewer)` | `None` | reviewing → approved. |
| `publish(skill_id, *, ctp_tx_id=None)` | `None` | approved → published (records CTP receipt). |
| `deprecate(skill_id, *, reason="")` | `None` | → deprecated. |
| `revoke(skill_id, *, reason="")` | `None` | → revoked. |

### `ClaimGuard(registry, proof)`
| Method | Returns | Notes |
|--------|---------|-------|
| `verify_claim(text, *, capability_id=None)` | `ClaimVerdict` | `supported`, `lifecycle`, `language`. Scoped downgrade for degraded capabilities (e.g. "degraded on macos only … not globally revoked"). |

### `WorkflowProofEngine(conn, foundry, proof)`
| Method | Returns | Notes |
|--------|---------|-------|
| `evaluate(workflow_id, workflow_version, component_skill_ids)` | `WorkflowProof` | candidate. Does NOT inherit component verification. |
| `record_evidence(...)` | `None` | Adds integration/failure/output evidence. |
| `validate()` | `bool` | Promotes candidate → validated when evidence sufficient. |

### `KnowledgeBubbleRuntime(conn, foundry)`
| Method | Returns | Notes |
|--------|---------|-------|
| `build_bubble(bubble_id, *, skills=None, procedures=None, claims=None, trust_metadata=None, exported_namespaces=None, ...)` | `dict` | v2 manifest (format_version=2, manifest_hash, artifact_inventory, …). |
| `import_bubble(bubble)` | `str` | ALWAYS quarantined. |
| `validate_bubble(bubble_id)` | `BubbleValidationReport` | 12-step (manifest before payload). |
| `approve_bubble(bubble_id, *, actor)` | `None` | quarantined → approved. |
| `install_bubble(bubble_id, *, ctp_tx_id=None)` | `None` | approved → installed (CTP-governed). |

### `Governance(conn, ctp, *, foundry, registry, bubbles)`
| Method | Returns | Notes |
|--------|---------|-------|
| `publish_skill(skill_id, actor, *, reason=None)` | `CTPReceipt` | Wraps publish in CTP. |
| `deprecate_capability(...)` / `revoke_capability(...)` | `CTPReceipt` | Wraps in CTP + audit. |

### `SkillCurator(foundry)`
| Method | Returns | Notes |
|--------|---------|-------|
| `curate()` | `list[CurationFinding]` | Detects duplicate/overlap/unsafe_perm/missing_verify/obsolete. |
| `recommend()` | `dict` | {total, critical, warnings, info, action_required}. |

---

## Errors

All raise subclasses of `CaptSoloError`:
`MemoryError_`, `TransactionError`, `IdempotencyError`, `BusError`,
`IntegrityError`, `ConfigurationError`, `MigrationBackupError`.
