# CAPT Memory Trigger Verification Report (M1-memory, ADR-DT-M1-MEM-001)

## Final status

**CAPT_MEMORY_TRIGGER_PROVEN**

## Conditions (all met)

- [x] mandatory memory is active (`MemoryTriggerEngine` wired into runtime + DriverHost)
- [x] 32k-step configuration works (`TRIGGER_INTERVAL_TOKENS = 32768`; steps 1..8)
- [x] harness conformance passes (reference driver + DriverHost, no Hermes)
- [x] genuine Hermes conformance passes (real `/Users/knowurknot/.local/bin/hermes` v0.19.1)
- [x] Desktop control works (`update_memory_trigger_policy` + GUI Tab 5)
- [x] ContextPack is mandatory (dispatch gate refuses without it)
- [x] trigger state persists and replays (`memory_policy_log` + `memory_trigger_log`)
- [x] no stateless fallback exists (gate raises `CONTEXTPACK_REQUIRED`)
- [x] promotion is governed (`evaluate_promotion` / `accept_promotion`, evidence-gated)
- [x] exact-SHA evidence exists (this report + `CAPT_MEMORY_TRIGGER_EVIDENCE_MANIFEST.json`)
- [x] draft PR is open (PR #31, branch `feat/capt-memory-trigger-integration`)

## Trigger interval

32,768 tokens (fixed).

## Configured steps (default effective policy)

| Trigger | Steps | Tokens |
|---|---|---|
| retrieval | 8 | 262,144 |
| compression | 8 | 262,144 |
| checkpoint | 8 | 262,144 |
| consolidation | 8 | 262,144 |
| hardStop | 8 | 262,144 |
| modelSafeLimit | 8 | 262,144 |

Operator may narrow any trigger (e.g. retrieval=1 → 32,768 tokens) via the
governed command; cannot widen past the model safe limit.

## Accounting method

`chars/4.0` estimate, labeled ESTIMATED, method recorded
(`capt_runtime/memory/accounting.py`).

## Test results

- Harness: 43 trigger tests + 16 adversarial tests = 59 passing.
- Hermes: 10 tests passing (4 real multi-setting dispatches + 6 boundary tests).
- Desktop: 5 tests passing.
- Full `tests/capt_runtime`: **251 passed**.

## Reference / Hermes swap proof

Same `MemoryTriggerEngine` logic drives both the reference driver path and the
Hermes driver path. `test_removal_of_hermes_does_not_break_trigger_logic` proves
equivalent CAPT semantics without Hermes.

## Memory query result

Mandatory `MemoryQuery` carries mission/task/run IDs, actor, requesting
subsystem, trigger boundary, context usage, requested classes, project scope,
purpose, relevance, time range, trust threshold, consent scope, sensitivity
allowance, record limit, token budget, provenance requirement, correlation ID,
causation ID. Records returned carry full governance metadata (no anonymous
blobs).

## ContextPack result

Idempotent `build_context_pack` records policy version, trigger boundary, usage
before/after, selected/excluded, exclusion reasons, compression actions,
summaries, provenance retention, unresolved conflicts, stale records,
redactions, token budget, digest, previous digest, mission/task/run IDs. Digest
is `sha256:` over the semantically meaningful fields.

## Promotion result

`evaluate_promotion` returns candidates with `requiresEvidence=True`,
`verified=False`. `accept_promotion` persists a record with
`trust=unverified`, `verification_status=pending`. Unverified output is never
promoted as verified fact.

## Reconnect / replay result

`reconstruct_policy(version)` rebuilds the exact effective policy from
`memory_policy_log`. `last_context_pack(mission_id)` returns the recorded pack.
Idempotent trigger state prevents duplicate retrieval/promotion on replay.

## Security findings

See `CAPT_MEMORY_TRIGGER_SECURITY_REVIEW.md`. All 16 adversarial vectors have
mitigations and passing tests.

## Residual risks

- Token estimate is heuristic (labeled ESTIMATED).
- Hermes is untrusted; its output is `trust=untrusted` and cannot alter policy.
- Memory store is SQLite (ledger-family); swappable for shared ledger in
  multi-process CAPT.

## Explicit confirmation

No stateless fallback, M2, packaging, Mode B, or repository-write automation
was started. This deliverable is the M1-memory trigger system only.
