# CAPT #168 — Durable Diagnostics and Council Receipt Repair (2026-10-08)

## Historical evidence and explicit uncertainty

Ouroboros R6 returned an accepted outer council receipt, but both inner cohort receipts were rejected with PROVIDERDRIVERFAILURE. GLM dr-model-a312307e37ef5132fd0b9616 had seven request_started boundaries and six response_completed boundaries. Qwen dr-model-c74d42413049a0c1cc148886 had two starts and one completed response. Both remained lost/reconciliation_required, with no result_persisted or final research artifact. They were not retried during the diagnostic repair.

## Code integration

- capt_runtime/diagnostic_receipts.py: safe allowlisted failure codes, phases and numerical HTTP statuses; a hashed model identifier; no raw exception string, prompt, credential, tool output or response body; bounded sanitized cohort receipt.
- capt_runtime/store.py: two authenticated-encrypted local SQLite projections for provider_failure_diagnostics and council_receipts. Writes use BEGIN IMMEDIATE transactional locking. A council ID has one immutable submission digest; each cohort writes an independent durable result. These are encrypted local projections, NOT hash-chain events.
- desktop/m1_command_service.py: claim a council before dispatch, reject altered-payload reuse, avoid replay on reattachment, persist sanitized per-cohort terminal receipts as each completes.
- desktop/capt_runtime_service.py: capture sanitized diagnostic before moving uncertain provider runs to lost/suspended; add authenticated read-only council_receipt and provider_failure_diagnostic queries.
- capt_runtime/drivers/provider.py: categorize HTTP status, timeouts, network failures and physical-budget rejection; do not propagate an upstream error body into receipt text.

## Recovery and safety semantics

- The retrieved council receipt includes sanitized complete operational status per cohort, NOT a raw model result archive. Terminal council execution can contain failed cohorts.
- A partially persisted in_progress council after a crash is ambiguous; it is not proof of an active provider process. Repeat submissions never authorize new inference.
- Provider diagnostics are recorded only for future errors after RuntimeService is reloaded. Neither GLM nor Qwen's historical missing final upstream response, billing status, or exact original exception can be reconstructed. Their lost states remain authoritative.
- Provider-reported cost may be unknown. Recording unknown is not a proved dollar cap. No provider calls are part of diagnostic tests.

## Three validation passes

1. Correctness: cross-run isolation, unique council identity, per-member settlement, immutable diagnostics, final vs failed result separation.
2. Adversarial: upstream error secrets discarded, malformations reduced to allowlisted codes, duplicate ID conflict, concurrent settlement and no automatic replay.
3. Recovery: reopen encrypted state, recover partial council, inspect terminal receipt over authenticated IPC after controlled runtime restart, run targeted and broad regression tests.

Status: local source implementation pending final full-suite and live restart evidence. Do not claim deployment or recovered GLM/Qwen analysis until verified.

## Verified live activation and regression receipts

- Full selected Python runtime regression suite: 1,374 passed, 13 skipped, 12 deselected, 0 failures (2026-10-08).
- Supplementary focused diagnostics/provider/authority tests: 66 passed, zero failures. The CLI child working-directory regression: 2 passed.
- CAPT launcher defect: capt_cli.py previously spawned the background -m desktop.capt_runtime_service without explicit cwd. RuntimeService restarted HEALTHY but imported an older code checkout; new query operations and tables were absent. The CLI now pins child cwd to Path(__file__).resolve().parent. Added tests/test_cli_runtime_environment.py regression.
- The corrected launcher restarted the live RuntimeService HEALTHY; authenticated query capabilities now report both council_receipt and provider_failure_diagnostic. Both encrypted tables are present in ~/.capt/runtime.db.
- CAPT authoritative ledger integrity remains ok; headSequence 23497 and chain digest sha256:ef7bd4795c9964c594ff8fd57c183cda033dc1d9a7b2855e5269a3ac3dc59272. Zero active DriverRuns before restart.
- Historical GLM dr-model-a312307e37ef5132fd0b9616 and Qwen dr-model-c74d42413049a0c1cc148886 are unchanged: lost/request_started. New failure-diagnostic lookup returns null for both, and historical R6 council lookup returns null, as expected: the feature is not retroactive.
- No billable provider inference was invoked for implementation, validation, or activation. The new storage now works for future CAPT execution attempts.

## Remaining operational gates

- Current implementation is local in the CAPT_core working tree and not yet committed/pushed upstream. Other unrelated local modifications were preserved.
- The new diagnostic projections are AES-GCM encrypted but are not part of the EventStore event hash-chain. The result and provider-billing certainty still depend on external evidence and ClaimGuard verification.
- Do not auto-rerun stranded GLM/Qwen tasks or promote their missing artifacts.
