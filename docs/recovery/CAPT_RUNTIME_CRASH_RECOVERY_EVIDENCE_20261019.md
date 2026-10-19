# CAPT Runtime Release and Crash Recovery — Evidence Boundary

Date: 2026-10-19  
Status: **PARTIAL; PRODUCTION ACTIVATION BLOCKED**  
Repository baseline: `0fee6655a33cd7d69162a4d8404cd332485d1e29`

## Observed production evidence

Read-only authenticated RuntimeService census:
- EventStore head 28252; integrity `ok`; digest `sha256:0335c62de9ddbee8eab92609f0ad1e397532b7549e64958aca13eeb04b53f9c4`.
- Active installed source `9906bf5fd71ec61a8feb3ea078dd26857703acb1`.
- Staged wheel candidate `0fee6655a33cd7d69162a4d8404cd332485d1e29`; nine source-to-installed-module digests independently matched during prior staging.
- Reservations: 2 `open`, 179 `awaiting_reconciliation`, 1023 `finalized`. No active running or queued DriverRuns were found.
- The old installed checkpoint reports only two open reservations; the repaired source counts 181 unresolved reservations. Authenticated readiness therefore reports `eligibleForQuiescence=false` with `CHECKPOINT_RECOVERY_NOT_CLEAN`, `RESERVATION_PROJECTION_MISMATCH`, and `UNRESOLVED_RESERVATIONS`.
- The Qwen scheduler reservation `res-cmd-85e8037f6a096feb` is linked to DriverRun `dr-cf1b9c47a5fa40cdb486`, which reached running and was cancelled on September 24.
- The MiMo retry reservation `res-cmd-fdd55e9fdd0dc3cd` is linked to DriverRun `dr-apex-mimo26pro-retry-20261007-r3`, which reached running and was cancelled on October 7.
- Neither historical reservation has a finalization record or matching ToolExecution under the exact task. Their external outcomes cannot be inferred from cancellation or absent historical provider-boundary events.

## Changes in this branch

- The reversible-switch journal pins the previous source SHA before moving the active runtime.
- An interrupted swap can be restored under a fresh governed preflight bound to the recorded checkpoint sequence/digest and state root.
- Rollback completion requires authenticated independent postcheck of the restored source and EventStore continuity.
- Journal writes use distinct temporary paths, so abandoned temp files from a crash cannot block a future recovery.
- A read-only authenticated readiness collector checks service identity, ledger head, sealed checkpoint, unresolved reservations, and active execution.

## Evidence and limitations

Subprocess crash tests cover process death after moving the old runtime, after moving the candidate, and during postcheck, plus denied recovery when authentication is missing. These use synthetic isolated filesystem fixtures; they **do not** certify a live daemon cutover.

**Not completed:** actual authenticated process-stop/upgrade/start/rollback integration in a fresh isolated CAPT service; physical crash injection into that service; independent production post-restart witness; adjudication of 181 historical unresolved reservations.

No code in this branch automatically consumes approvals, retries provider calls, edits historical EventStore outcomes, overrides release gates, or activates the staged candidate. Production activation remains blocked until the evidence and independent release tests are complete.

Related: #180, #185, #210, #245.
