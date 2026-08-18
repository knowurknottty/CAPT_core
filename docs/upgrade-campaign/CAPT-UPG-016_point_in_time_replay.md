# CAPT-UPG-016 — Point-in-Time Replay + Linear Governed Replay Fork

- **Campaign ID:** `CAPT-UPG-016`
- **Issue:** #102
- **Base:** verified CAPT-UPG-015 @ `37fe76e02eb4609ef4c9a24439ce4ad53f08492a`
- **Disposition before exact-commit gate:** `IMPLEMENTED_PENDING_EXACT_COMMIT_VERIFICATION`

## Point-in-time replay correction

The previous `checkpoint_replay()` seeded historical stream versions with present-day aggregate snapshots. If a stream changed after the checkpoint, tail replay could begin from future state and produce invalid or misleading reconstruction.

The corrected implementation adds `replay_to_sequence()` and makes checkpoint replay reconstruct the actual append-only ledger prefix through the checkpoint position before folding the tail.

Historical checkpoint binding now verifies all of:

- requested global sequence exists;
- reconstructed checkpoint stream versions equal manifest versions;
- ledger prefix chain digest equals `ledgerDigest`;
- prefix head event ID equals `ledgerPosition.eventId`.

A self-consistent manifest digest cannot authorize a false historical ledger anchor.

## Linear governed fork

`ReplayForkAggregate` records provenance for a new continuation:

- source global sequence;
- source event ID;
- source replay-state digest;
- exact source ledger-prefix chain digest;
- new mission ID;
- human actor/reason/time;
- explicit `historicalAuthorityReactivated: false`.

`RuntimeService.create_replay_fork()` atomically appends `ReplayForkCreated` and creates a **new draft Mission**. It never truncates or rewrites source history and never copies historical capability grants, leases, approvals, tasks, or DriverRuns into the new continuation.

The authenticated operator path forwards a high-level `ReplayForkIntent`; RuntimeService builds MissionSpec. Fork creation refuses `requiresApproval=true` so approval authority cannot be smuggled through the fork transaction.

## Operator surfaces

- `replay_state_at`: read-only deterministic historical query;
- `create_replay_fork`: authenticated governed command;
- shared `Operator.replay_state_at()` and `Operator.create_replay_fork()` methods;
- runtime capability discovery advertises both operations.

## Contract integration

- `replay_fork-*` stream IDs;
- `ReplayForkCreated` EventEnvelope payload;
- typed `ReplayForkState` and `ReplayForkIntent` contracts;
- generated Python/TypeScript bindings;
- valid cross-language ReplayFork event fixture.

## Adversarial coverage

Tests cover:

- the reproduced post-checkpoint future-snapshot bug;
- false ledger digest anchor;
- false checkpoint event ID anchor;
- read-only historical query with no mutation;
- new-history fork without historical authority reactivation;
- exact idempotent retry;
- conflicting idempotency-key reuse;
- wrong authenticated identity;
- future/nonexistent source sequence;
- attempted approval-authority smuggling;
- source historical state and chain-prefix identity unchanged after fork creation.

## Pre-commit verification

```text
DRIFT CHECK: OK (11 generated files match the schema source)
focused replay/contract/operator gate: 33 passed
full non-slow suite: 989 passed, 13 skipped, 12 deselected
```

Exact-commit verification is performed immediately after this evidence/code commit and recorded on the PR. Tests marked `slow` remain outside the repository default gate.
