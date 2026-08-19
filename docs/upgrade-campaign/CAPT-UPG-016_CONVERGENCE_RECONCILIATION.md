# CAPT-UPG-016 Convergence Reconciliation

Date: 2026-08-19

Integration branch: `integration/capt-core-main-convergence-r1`

CAPT provenance mission: `mission-main-convergence-7f16527a311c`

## Disposition

`IMPLEMENTED_ON_CURRENT_NATIVE_PROVIDER_SPINE_WITH_CHECKPOINT_CORRECTION`

No release or merge authorization is implied.

## Exact historical replay defect reproduced

Before this convergence slice, `checkpoint_replay()` trusted the checkpoint version numbers but loaded each stream with `EventStore.load_state()`, which returns the **present-day** aggregate snapshot.

A discriminating RED test proved the contradiction:

1. a task was `running` at the checkpoint;
2. the same task later transitioned to `succeeded`;
3. checkpoint replay seeded the old task version with the current `succeeded` state;
4. tail replay then attempted `succeeded -> succeeded` and failed as an illegal transition.

The old implementation therefore did not reconstruct point-in-time state faithfully.

## Corrected replay model

`replay_to_sequence()` now folds the verified append-only ledger from origin only through the requested `globalSequence`. It never seeds historical state from current aggregate snapshots.

`ledger_identity_to_sequence()` independently derives the exact ledger-prefix identity:

- `globalSequence`;
- head `eventId` at that prefix;
- chain digest through that exact event.

Checkpoint replay now:

1. validates the manifest itself;
2. reconstructs exact state through the checkpoint sequence;
3. proves the manifest `ledgerDigest` equals the real ledger-prefix chain digest;
4. proves `ledgerPosition.eventId` equals the actual prefix event ID;
5. validates every version array present in the manifest against reconstructed historical versions;
6. folds only post-checkpoint tail events afterward.

A caller cannot make a forged ledger anchor valid merely by recomputing the checkpoint's self-integrity digest.

## Backward-compatible extension fields

The converged runtime already had optional bounded checkpoint arrays for:

- `humanApprovalVersions`;
- `artifactPromotionVersions`;
- `cohortVersions`.

UPG-016 adds optional `replayForkVersions` rather than restoring the historical branch's extension-from-origin workaround.

Older compatible manifests that predate an optional extension array remain readable because the exact ledger-prefix digest still binds all historical events, while version arrays that are present are checked explicitly.

## Governed linear replay fork

`ReplayForkAggregate` records provenance for a **new history**, not revived historical authority.

A human-authenticated `create_replay_fork` command binds:

- source sequence;
- source event ID;
- exact reconstructed source-state digest;
- exact source chain-prefix digest;
- a newly created draft Mission ID;
- operator identity/reason/time;
- `historicalAuthorityReactivated=false`.

RuntimeService builds the new MissionSpec from the high-level intent. Historical capabilities, leases, approvals, tasks, and DriverRuns are not copied or reactivated.

A replay-fork intent with `requiresApproval=true` is rejected rather than auto-creating approval authority. Future source positions, reused identities, wrong authenticated operator/session, and conflicting idempotent replays fail closed before mutation.

`replay_state_at` is a read-only RuntimeQueryService/Operator projection and does not mutate EventStore.

## RED -> GREEN evidence

The pre-implementation UPG-016 suite produced 12 failures, including:

- present-day snapshot contamination of checkpoint replay;
- missing point-in-time replay functions;
- acceptance of forged checkpoint chain/event anchors;
- absent historical query surface;
- absent governed replay-fork command.

After integration, the focused exact replay/fork/operator gate passed `22/22`.

## Broad verification

- Python repository: `1031 passed, 13 skipped, 12 deselected`;
- generated contract drift: `DRIFT CHECK: OK (11 generated files match the schema source)`;
- TypeScript fixture parity: PASS;
- Swift package: `54 executed, 4 explicit live-runtime skips, 0 failures`;
- `swift build --product CAPTNativeMac`: PASS;
- `git diff --check`: PASS.

## Remaining boundary

A replay fork is provenance plus a new draft mission. It is not a branch that inherits historical authority. Normal CAPT policy, approval, capability, execution, verification, ClaimGuard, and promotion transitions must establish any consequential authority after the fork.
