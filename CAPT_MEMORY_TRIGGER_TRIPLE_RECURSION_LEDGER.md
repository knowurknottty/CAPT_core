# CAPT Memory Trigger Triple Recursion Ledger (M1-memory, ADR-DT-M1-MEM-001)

## Pass 1 — Construct

Implemented the mandatory memory trigger system:

- **Forensic recovery** (Phase 1): classified all existing memory behavior.
  `capt_solo/memory/` (MemoryEngine, ContextPack, KnowledgeBubbleRuntime) is
  IMPLEMENTED_DISCONNECTED — separate lineage, not imported by `capt_runtime`.
  `capt_runtime` had zero memory modules. Decision: build a CAPT-owned
  `capt_runtime/memory/` subsystem (not a port of capt_solo).
- **Contracts**: `MemoryTriggerPolicy`, `MemoryQuery`, `MemoryRecord`,
  `ContextPack` added to `common.schema.json`; `ContextSlice.contextPackRef`
  and `ExecutionDriverWorkOrder.memoryPolicyRef` added to `driver.schema.json`.
  Regenerated bindings; drift clean.
- **Policy**: 32,768-token fixed interval; independent step counts per trigger;
  precedence enforcement (narrowing only); validation rejects zero/negative/
  non-integer/over-limit/non-multiple.
- **Accounting**: `ContextUsage` + `ContextAccounting` measure usage, compute
  next 32k boundary, label estimates ESTIMATED.
- **Store + query**: `MemoryStore` (SQLite) with consent/sensitivity gates;
  `build_memory_query` typed contract.
- **ContextPack**: idempotent `build_context_pack` with digest.
- **Engine**: `MemoryTriggerEngine` owns trigger state, dispatch gate
  (`require_memory_before_dispatch`), promotion, reconnect/replay.
- **Harness**: `DriverHost.dispatch` calls the gate.
- **Hermes**: `build_prompt` embeds only the ContextPack slice reference.
- **Desktop**: `update_memory_trigger_policy` command + GUI Tab 5.
- **Tests**: 74 memory tests (43 harness + 10 Hermes + 5 desktop + 16 adversarial).

## Pass 2 — Adversarial review

Challenged 16 vectors (token accuracy, off-by-one, duplicate firing,
suppression, Hermes override, smuggling, hidden memory, consent leakage, stale,
growth, replay, race, active-run change, model-limit mismatch, UI bypass,
stateless fallback). Each has a passing test in
`test_memory_trigger_adversarial.py` and `test_memory_trigger_hermes.py`.

**Defects found and fixed during construction:**

1. `MemoryStore` / `MemoryTriggerEngine` SQLite connections created in the
   server main thread but used in per-connection threads → "SQLite objects
   created in a thread can only be used in that same thread". Fixed with
   `check_same_thread=False` + `threading.Lock` on writes.
2. `row_factory = sqlite3.Row` dropped during a refactor → "tuple indices must
   be integers" on policy-version reads. Restored.
3. Consent/sensitivity exclusions were silently dropped at the SQL layer, not
   visible. Fixed: `_select_records` applies consent/sensitivity filtering in
   Python and reports exclusions; `store.query` gains `bypass_governance`.
4. `with_update` used `or` idiom → `retrieval_trigger_steps=0` silently fell
   back to current (accepted instead of rejected). Fixed with explicit
   `is not None` checks.
5. `update_memory_trigger_policy` receipt omitted token fields → desktop test
   expected `retrievalTokens`. Added token fields to the receipt.

## Pass 3 — Reconcile

All confirmed defects fixed and re-verified. Full `tests/capt_runtime` suite:
**251 passed**. No hidden reasoning exposed. Residual risks documented in
`CAPT_MEMORY_TRIGGER_SECURITY_REVIEW.md` and the evidence manifest.

## Residual uncertainty

- Exact tokenization unavailable; estimate is heuristic (labeled). Acceptable
  for the mandatory-trigger contract; measured tokens would tighten boundaries.
- Hermes is untrusted; its prompt receives only the slice reference. The driver
  cannot alter CAPT policy by construction (no policy surface).
