# CAPT Runtime Replay + Single-Authority Hardening — 2026-10-17

## Mission and authority

- Mission: `m-capt-runtime-replay-singleowner-hardening-20261017`; planned in authoritative RuntimeService; state at registration: **draft** (not falsely closed).
- Repository: `/Users/knowurknot/CAPT_core`, `main`, baseline HEAD `5608e8096132a93c45eabd6c0ac7e5bfb6bc8217`.
- Scope: replay and process ownership; no ledger rewriting, no grant bypass, no production restart, no push.
- CAPT Node capability observed expired as of October 17; local source recovery and tests were executed via Raw Commander. This work does **not** claim CAPT-governed execution.

## Implemented source changes

1. `capt_runtime/replay.py` folds all historical `ToolExecution*` events and `DriverRunDispatchBoundaryRecorded` using the canonical aggregate transition rules.
2. `capt_runtime/aggregates/tool_execution.py` re-derives every tool state from the prior state plus permitted mutable fields; an event snapshot differing from the derived state fails integrity validation.
3. `tests/capt_runtime/test_tool_execution.py` covers full/checkpoint replay equivalence and rejects forged tool identity or mismatched lifecycle state.
4. `tests/capt_runtime/test_runtime_replay_hardening.py` covers DriverRun boundary replay and rejects a second service process before socket/token mutation.
## Measured validation

- Expanded focused replay/restart tests, including stale Unix socket recovery: **22 passed**.
- Full `tests/capt_runtime` run: **1,454 passed, 13 skipped, 12 deselected, 1 failed**; failure solely `test_cross_language_fixture_parity`, due unavailable `tsc` in the default PATH.
- Used already-cached, offline TypeScript **5.9.3** to compile generated contract bindings; isolated parity rerun **1 passed**. No npm installation or network retrieval.
- Final independent complete suite with cached TypeScript compiler on PATH: **1,455 passed, 13 skipped, 12 deselected, 0 failed**, 175.03 seconds. This supersedes the earlier environment-only failure for acceptance purposes.
- Live-ledger dry replay on head **25,353**: **25,353 events applied, 5,626 streams**, no missing reducer/error.
- All **2,509 ToolExecution** aggregate states reconstructed equal to the materialized state; no ToolExecution kind appeared in the difference classification.
- The existing single-owner file lock is retained (not replaced). Process-level regression confirms a second RuntimeService fails before changing the listening socket or auth token.

## Historical projection drift — not silently normalized

Strict replay-to-stored-state comparison found **1,943 differences**:
- 649 capabilities, 496 HumanApprovals, 435 DriverRuns, 362 Missions: historical projections omit optional fields now added by current constructors (empty/default-valued fields).
- 1 Task: `task-m-capt-issues-20260924-live-task-1` has stored `assignedDriverId='capt-node'`; no event in its stream records that assignment.

The final Task discrepancy cannot be repaired from the event history without inventing data. Optional-field differences require a version-aware compatibility policy, not a blanket mutation of historical records. Full byte-for-byte materialized-state equivalence is **not established**.
## Closure gates and further work

- [x] Runtime event vocabulary recognized and replayed deterministically
- [x] ToolExecution state parity and adversarial mutation rejection
- [x] Process-level exclusive-lock contention and stale socket recovery proofs
- [x] Focused Python tests passing
- [x] Cross-language contract parity after offline TypeScript build
- [ ] Approve an explicit historical schema-compatibility policy and quantify any remaining semantic drift
- [ ] Recover/attest the historical task assignment from external evidence, or retain it as unprovable
- [ ] Obtain fresh CAPT Node execution authority and run governed adoption/independent acceptance
- [ ] Confirm a safe production release window; active RuntimeService was not restarted

**Completion claim:** candidate source fix tested; mission not promoted to completed in CAPT; no production deployment or Git push claimed.
