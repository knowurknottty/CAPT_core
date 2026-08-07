# CAPT Standalone Harness v0.5 — Treasure Chest Function Reconciliation

Date: 2026-08-05
PRE_REPAIR_INSTALLED_CANDIDATE_SHA: b45c4b005c9171172d055697a55034006bb0f2fe
VERIFICATION_REPAIR_SHA: b79c4f05784d001268e3fef523755365b1f5888e
CURRENT_LOCAL_HEAD: b79c4f05784d001268e3fef523755365b1f5888e
BRANCH: release/capt-standalone-final
REMOTE: REMOTE_STATE_UNVERIFIED (release/capt-standalone-final not found on origin)
ATTRIBUTION: knowurknot

## Canonical Source Priority

1. Current release branch source and tests (release/capt-standalone-final)
2. Installed artifact behavior (wheel sha256 348fe9da...)
3. Frozen contracts and schemas (contracts/schema/*.json)
4. Current release documentation (docs/, README.md)
5. Historical architecture documents (docs/architecture/)
6. Commit history and branch evidence
7. Narrative handoffs (evidence-manifest.md, operator-handoff.md)

## Previous Draft Invalidated

An earlier draft of this document (in [[_quarantine/INVALIDATED_DRAFTS/06 — Treasure Chest Function Reconciliation.md]]) classified KHSB, CTP, and CAPT memory as NOT PRESENT based on zero search-tool results. This was an audit-method failure (see INVENTED_ACRONYM_EXPANSION and ABSENCE_CLAIM_WITHOUT_CANONICAL_SEARCH below). Direct repository tree inspection reveals all three modules exist and ship in the installed wheel.

## Function Matrix

### CAPT Solo Memory Engine (Plane A)
- **Canonical source**: capt_solo/memory/engine.py on release/capt-standalone-final
- **Module docstring**: "Memory Engine implementation. Storage is SQLite (single file, human-readable via .dump / JSON export). The schema is versioned (schema_version table)"
- **Public API**: store, get, update, delete, search, list, export_json, import_json, backup, restore, integrity_check, set_search_adapter
- **Features**: namespaces, tags, provenance, confidence, metadata, backups, import/export, integrity checks
- **Public re-export**: capt_solo/api.py re-exports MemoryEngine-related types
- **Installed wheel**: capt_solo/memory/engine.py IS IN the wheel (sha256 348fe9da...)
- **Tests**: capt_solo memory tests exist in the test suite
- **Classification**: IMPLEMENTED_IN_CAPT_SOLO_MAIN — INSTALLED_WHEEL_CONTENT_CONFIRMED — CLI/OPERATOR_REACHABILITY_NOT_YET_RECONCILED

### Runtime EventStore Continuity (Plane B)
- **Canonical source**: capt_runtime/store.py on release/capt-standalone-final
- **Behavior**: SQLite WAL mode EventStore; mission/task/session aggregates; checkpoint manifests; replay; chain digest verification; restart reconstruction; no-repeat behavior
- **Installed proof**: PROVEN_BY_INSTALLED_ARTIFACT — ledger grew 0->13->26->39 events; chain digest matched on restart; resume returned not_repeated
- **Classification**: IMPLEMENTED_AND_INSTALLED_PROVEN

### Checkpoint / Replay
- **Canonical source**: capt_runtime/checkpoint.py; checkpoint.schema.json
- **Installed proof**: PROVEN_BY_INSTALLED_ARTIFACT — checkpoint manifest created, restart verified, resume not_repeated
- **Classification**: IMPLEMENTED_AND_INSTALLED_PROVEN

### Memory Trigger Policy (Plane C)
- **Canonical source**: capt_runtime/memory/policy.py on release/capt-standalone-final
- **Module docstring**: "MemoryTriggerPolicy model and 32k-step validation (ADR-DT-M1-MEM-001). The trigger interval is a FIXED 32,768 tokens."
- **Frozen contract**: contracts/schema/common.schema.json defines MemoryTriggerPolicy with triggerIntervalTokens const: 32768
- **Trigger types (independent 32k steps)**: retrieval, compression, checkpoint, consolidation, hardStop, modelSafeLimit
- **Supported ladder steps**: [1, 2, 3, 4, 5, 6, 7, 8] (32k through 256k)
- **Precedence**: constitutional > runtime_policy > model_provider > project_policy > operator_selected > driver_preference
- **Installed wheel**: capt_runtime/memory/policy.py IS IN the wheel
- **Tests**: tests/capt_runtime/test_memory_trigger_hermes.py (12 tests; deselected with -m 'not slow' but individually proven in prior sessions)
- **Classification**: IMPLEMENTED_IN_SOURCE_AND_WHEEL — INSTALLED_CLI_REACHABILITY_PROVEN (update_memory_trigger_policy governable command exercised in installed lifecycle)

### ContextPack
- **Canonical source**: capt_runtime/memory/contextpack.py; contracts/schema/common.schema.json ContextPack definition
- **Contract**: ContextPack requires contextPackId, policyVersion, triggerBoundary, selectedRecords, excludedRecords, tokenBudget, contextPackDigest
- **ContextSlice integration**: driver.schema.json ContextSlice has contextPackRef (contextPackId + contextPackDigest)
- **Installed wheel**: capt_runtime/memory/contextpack.py IS IN the wheel
- **Dispatch gate**: driver_host.py validates contextPackRef on dispatch; blocks dispatch without ContextPack
- **Classification**: IMPLEMENTED_IN_SOURCE_AND_WHEEL — INSTALLED_CONTRACT_PRESENT

### 32K Trigger Ladder
- **Canonical source**: capt_runtime/memory/policy.py TRIGGER_INTERVAL_TOKENS = 32_768; SUPPORTED_LADDER_STEPS = [1..8]
- **Contract**: MemoryTriggerPolicy.triggerIntervalTokens const: 32768 (frozen schema)
- **Context accounting**: capt_runtime/memory/accounting.py computes next 32k trigger boundary
- **Architecture doc**: CAPT_MEMORY_TRIGGER_ARCHITECTURE.md describes independent 32k steps at 32k/64k/96k/128k
- **Tests exercised at**: 32k/64k/96k/128k via parametrize("steps", [1,2,3,4])
- **Classification**: IMPLEMENTED_IN_SOURCE_AND_WHEEL — INSTALLED_CONTRACT_PRESENT

### MemoryGovernor (Plane D)
- **Canonical source**: capt_runtime/memory/governor.py on release/capt-standalone-final
- **Module docstring**: "MemoryGovernor — plugin-triggered, threshold-enforced context governor. This is NOT a voluntary-call governor. The model is not a reliable trigger source. Plugin hooks (pre_llm_call / post_llm_call / on_session_end) are the ONLY trigger mechanism."
- **Features**: Maintain deterministic context estimator; Enforce SOFT/HARD/EMERGENCY thresholds BEFORE Hermes native compaction; Offload exact governed state to CAPTMem with immutable references/digests; Compile bounded ContextPack from persisted records; Reinjection or durable session handoff without operator restatement
- **Semantic distinctions**: HERMES_COMPRESSION (lossy, UNTRUSTED) / CAPTMEM_OFFLOAD (exact, TRUSTED) / CONTEXTPACK_REHYDRATION (bounded working context)
- **Installed wheel**: capt_runtime/memory/governor.py IS IN the wheel
- **Classification**: IMPLEMENTED_IN_SOURCE_AND_WHEEL — INSTALLED_CLI_REACHABILITY_NOT_YET_RECONCILED (governor triggers via plugin hooks, not direct CLI command)

### KHSB — Knowledge/Hermes Signal Bus
- **Canonical name**: KHSB (canonical expansion found in module docstring: "KHSB — Knowledge/Hermes Signal Bus")
- **Canonical source**: capt_solo/khsb/bus.py on release/capt-standalone-final
- **Module docstring**: "An in-process, networking-free message bus. All communication stays inside the current process; no sockets, no files, no external brokers. This is the v0.1 foundation. Distributed transport (remote agents, federation) is a future extension point and is NOT implemented here."
- **Public API**: publish(topic, payload, correlation_id), subscribe(topic, handler), unsubscribe, request(topic, payload, timeout), reply(request_event, payload), ack(message_id), pending_messages(topic)
- **Public re-export**: capt_solo/api.py re-exports KHSB, Message
- **Installed wheel**: capt_solo/khsb/bus.py IS IN the wheel (sha256 348fe9da...)
- **Classification**: IMPLEMENTED_IN_CAPT_SOLO_MAIN — INSTALLED_WHEEL_CONTENT_CONFIRMED — CLI/OPERATOR_REACHABILITY_NOT_YET_RECONCILED

### CTP — Cognitive Transaction Protocol
- **Canonical name**: CTP (canonical expansion found in module docstring: "Durable local Cognitive Transaction Protocol journal")
- **Canonical source**: capt_solo/ctp/journal.py on release/capt-standalone-final
- **Module docstring**: "The journal is append-only JSONL under the CAPT runtime home. It provides recoverable begin/validate/note/commit/abort semantics and immutable receipts."
- **Features**: append-only local journaling, begin/validate/note/commit/abort, immutable receipts, idempotency keys, recovery of unfinished transactions, audit trails, integrity checks
- **Public re-export**: capt_solo/api.py re-exports CTPRuntime, Receipt
- **Installed wheel**: capt_solo/ctp/journal.py IS IN the wheel (sha256 348fe9da...)
- **Classification**: IMPLEMENTED_IN_CAPT_SOLO_MAIN — INSTALLED_WHEEL_CONTENT_CONFIRMED — CLI/OPERATOR_REACHABILITY_NOT_YET_RECONCILED

### Model Operator
- **Canonical source**: capt_runtime/drivers/hermes.py (HermesDriver); capt_runtime/task_resolver.py (TaskResolver); capt_runtime/driver_host.py (DriverHost)
- **Commits**: 7475dcf (resolve driver tasks from authoritative task references), 554ff15 (expose governed Hermes model operator), cb8089d (advertise governed Hermes model operator capability), ac6d057 (grant artifact.create lease), 3aa1be5 (drop non-contract field), 6737f2c (ClaimGuard allowlisted claim), b45c4b0 (idempotency conflict rejection)
- **Installed proof**: PROVEN_BY_INSTALLED_ARTIFACT — 3 real Hermes model tasks through installed wheel; TaskResolver proven; bounded prompt derived inside CAPT; ClaimGuard applied; checkpoint/stop/restart/resume proven
- **Classification**: IMPLEMENTED_AND_INSTALLED_PROVEN (bounded read-only repository inspection) — GENERAL_MODEL_DRIVEN_ENGINEERING_REMAINS_UNPROVEN

### Bytecode
- **Canonical source**: TERRA directive prohibits bytecode in v0.5 scope
- **Classification**: DEFERRED_BY_CURRENT_RELEASE_SCOPE — not "prohibited" (deferred)

### Encryption / Dual-Layer Encryption
- **Canonical source**: TERRA directive prohibits new encryption layers in v0.5 scope
- **Classification**: DEFERRED_BY_CURRENT_RELEASE_SCOPE — not "prohibited" (deferred)

### ECP v0.6
- **Classification**: DEFERRED_POST_RELEASE

### Cross-Model Resume
- **Classification**: NOT_YET_RECONCILED — resume is proven (not_repeated) within same driver/backend; cross-model resume mechanism not identified in current evidence

## Audit Failure Modes Encountered and Corrected

### INVENTED_ACRONYM_EXPANSION — ENCOUNTERED, CORRECTED
The quarantined draft invented expansions: "knowledge-heap snapshot buffer" for KHSB, "capture-transfer-protocol" for CTP. Canonical expansions found: KHSB = Knowledge/Hermes Signal Bus; CTP = Cognitive Transaction Protocol.

### ABSENCE_CLAIM_WITHOUT_CANONICAL_SEARCH — ENCOUNTERED, CORRECTED
The quarantined draft classified KHSB, CTP, and memory systems as NOT PRESENT based on zero search-tool results. Direct repository tree inspection (git ls-tree, module docstring reading, wheel contents enumeration) revealed all three modules exist, are implemented, and ship in the installed wheel. The search tool returned zero hits for terms whose files are confirmed to exist — a known failure mode. Rule: ZERO_SEARCH_RESULTS != FEATURE_ABSENT.

## Remaining Unresolved

- CAPT Solo memory engine, KHSB, and CTP CLI/operator reachability through the installed harness CLI is NOT YET RECONCILED. The modules ship in the wheel but their governance/exposure via `capt harness` commands is not independently proven this session.
- Hermes compression interception / CAPTMem extension (Plane D) is implemented as MemoryGovernor module but its plugin-hook activation path has not been exercised in the installed lifecycle proof.
- Full Treasure Chest specification cross-reference (knowurknottty/captstreasurechest repo) was not performed against each capability row body.
