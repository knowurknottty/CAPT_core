# Hermes Restart / Reconciliation Report

Evidence: `artifacts/hermes-integration/e2e_proof_run.json`

## Checkpoint

| Field | Value |
|---|---|
| Checkpoint id | `cp-hermes` |
| Events applied (full replay) | 8 |
| Events applied after checkpoint (tail replay) | 0 |
| `replay_equivalent(full, tail)` | true |

## Separate-process restart

Replay was performed in a **different OS process** (`python -m
tests.capt_runtime.restart_process <db>`), not merely a new object in the same
interpreter.

```
exit code: 0
{"equivalent": true,
 "full_applied": 8,
 "replay_applied": 0,
 "full_digest":   "sha256:b82feb61ce120acf71d420e7074d7f657b6d7a57b0b73e290f12dd5b90e5c3e1",
 "replay_digest": "sha256:b82feb61ce120acf71d420e7074d7f657b6d7a57b0b73e290f12dd5b90e5c3e1"}
```

Digests are identical. No duplicate execution occurred: `replay_applied` is 0
after the checkpoint, meaning replay reconstructed state from the checkpoint
rather than re-running the driver.

## Reconciliation

| Case | Result |
|---|---|
| Completed run, artifact present, lease valid, budget valid | `reconciled_completed` |
| Unknown run at the driver (simulating a CAPT restart with no driver memory) | `external_state_unknown` with an anomaly recorded — never a success assertion |
| Replay after cancellation | terminal; refuses to re-drive to running (frozen test) |
| Replay after reconciliation | terminal (frozen test) |

`HermesDriver.reconcile` for a run it has never seen returns
`external_state_unknown` with `anomalies: ["driver has no local record of this
run"]`. This is the correct behaviour after a CAPT process restart: the driver's
in-memory map is empty and CAPT must reconcile from its own ledger, not from
driver testimony.

## Cancellation

`cancel(run_id, reason)` sends SIGTERM to the process **group** (the child is
launched with `start_new_session=True`, so its descendants are included) and
marks the run cancelled. `resume` on a cancelled run raises
`HermesDriverFailure`. Unknown run ids raise `KeyError` on both `inspect` and
`cancel` rather than silently succeeding.
