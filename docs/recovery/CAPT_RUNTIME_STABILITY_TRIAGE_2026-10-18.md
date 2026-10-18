# CAPT runtime stability incident and scoped corrective work — 2026-10-18

## Authority and method

Incident assessed via authenticated CAPT RuntimeService IPC projections, CAPT Node governed read-only commands, isolated code/test worktree rooted at origin/main (957a710a), and independent installed-vs-source file digests. This audit is NOT an external model council, and it has made zero billable model inference requests. No production EventStore mutation, direct SQLite repair, provider credit spend, cancellation, credential access, or live runtime restart.

## OBSERVED: authoritative live runtime

- Source: authenticated RuntimeService projection, ledger-chain integrity = OK, headSequence = 27029 at baseline (subject to subsequent ordinary service activity).
- 416 missions: draft 1, cancelled 386, completed 25, authorized 4. **Cancelled is not a synonym for failed**; do not attribute 386 cancellations to the charter defect without case-by-case evidence.
- 491 tasks: pending 1, cancelled 406, succeeded 46, failed 36, suspended 2.
- Read all 36 failed task streams and 2 suspended task streams through RuntimeService:
  - 28 failed: "approval-bound Vessel Charter ledger incomplete".
  - 4 failed: "human review reject after independent ClaimGuard evaluation".
  - 4 failed: "restart before driver submission".
  - 2 suspended: "external dispatch outcome indeterminate; reconciliation required".
- 646 HumanApprovals: stored consumed 465, requested 68, revoked 18, approved 72, denied 23; **72 approved entries derivedStale** (stored state is not expired). Never consume or revoke them automatically; make stale distinct in UI/query.
- Live RuntimeService Python process was found executing from a runtime-venv site-packages installation, not dynamically importing the current CAPT_core checkout.
- In that installation, provider.py and cohort_contract.py digest differed from the newest merged Core source; checkpoint.py and desktop/capt_runtime_service.py matched. Live process remains an older loaded module until a governed release/restart.
- This is a chronic systemic charter-completion failure, not evidence that the ledger chain is corrupt.

## OBSERVED: independent council case studies

- DeepSeek strict charter structure passed; content identified only 37/43 authoritative backlog controls. Model source-absence claims contradicted the frozen six-file input.
- MiMo persisted all 43 control dispositions, but candidate ledger stopped mid-C0076; 75 candidate prefixes, zero selected vessels, no charter audit. Task properly failed post-inference. Historical finish reason is unavailable.
- GLM approval consumed once, but 5 physical provider HTTP request_started boundaries under one DriverRun; last boundary response_completed, DriverRun lost, reconciliation required; no persisted report. No automatic retry. More than one provider request was *permitted* despite a "one inference" virtual-council expectation. The number of billable provider results is UNKNOWN.
- CAPT_core DriverRunAggregate.MAX_PROVIDER_HTTP_REQUESTS_PER_RUN = 24, ModelToolBridge.MAX_TOOL_CALLS = 32, TokenCostGovernor default max_requests_per_session = 100: these are not a per-cohort human-bound physical budget.
- The post-response Vessel Charter validator correctly refuses incomplete results but cannot prevent provider credit consumption.

## CHANGED: isolated source repair in this branch only

1. Cohort normalization binds an explicit maxPhysicalProviderRequests to the immutable cohort specification and therefore HumanApproval digest. Strict-v2 charters default to **1** physical request; an operator can deliberately bind 2..24 in a future distinct approval. Values 0/negative/25, bool and noninteger fail before approval.
2. For strict one-request councils, the provider sends the already-approved frozen prompt without advertising a tool-call loop that *cannot* complete in one HTTP call. Other run types retain their existing tool mechanisms. No logical vessel is expanded into multiple physical calls.
3. The driver reserves a local per-run request slot before durable request_started and network I/O. Attempts beyond the bound fail closed pre-dispatch; the full durable EventStore boundary recording remains in place. No retry/replay path added.
4. A strict charter whose conservative output geometry exceeds the configured output-token ceiling is rejected before a provider call. This is a necessary safety gate, not proof that a model which passes will actually produce a complete response.
5. ToolBroker execution errors in the model's provider tool loop become a typed, sanitized PROVIDER_TOOL_FAILURE with phase tool_execution, without surfacing tool outputs, arguments or raw exception messages.
6. The original strict ledger-first instruction and persisted finish-reason improvements from earlier PR #211 remain intact. The validator still rejects fabricated/incomplete charters; no weakening of evidence requirements.

## VERIFY and remaining gates

- Focused cohort/provider/physical-budget suite: **61 passed** on the isolated Mac worktree, without provider network dispatch; changes passed focused Ruff and schema-generated drift checks before the typed diagnostic addition, to be re-run for the final SHA.
- Run broader Python regression and GitHub CI before merging. Initial M0-A CI exposed legacy tests expecting unsafe raw exception details in failed tool calls, and two direct _post_json test entry points without prepopulated process-local run state. Corrected the transient state initializer and updated the tests to assert sanitized failure receipts instead of promoting internal authority details across the response boundary. Confirm the new CI run and independently verify successful request-boundary evidence.
- Demonstrate prompt-assembly/approval parity including the new maxPhysicalProviderRequests bound under RuntimeService.
- Separately implement semantic exact-source/ID verification (issue #187); do not claim it is addressed by physical budget enforcement.
- Implement safe provider-effect reconciliation for lost runs and verify authenticated provider billing (issues #185/#210). Do not auto-replay lost GLM.
- The running RuntimeService is **not upgraded** by merging source. Deploy only with a governed quiescence/rollback mechanism, no active provider attempts, reversible vetted package build, snapshot/checkpoint evidence, post-restart authenticated IPC and stable ledger digest continuity. A blind pip install or kill/restart does NOT satisfy this gate.
- Do not automatically bulk-close 72 stale approved approvals or reclassify 386 historic cancellations; a separate non-destructive cleanup/reconciliation review is required.

## Reporting contract

OBSERVED means verified from RuntimeService or byte-source comparison. CHANGED means source/test files only. VERIFIED means passing named tests and commit receipts. UNPROVEN includes production deployment, backend charges, reconstructed lost model content, full mission completion, and release readiness.
