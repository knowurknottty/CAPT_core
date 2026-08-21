# CAPT-UPG-010–011 Convergence Reconciliation

Date: 2026-08-19

Integration branch: `integration/capt-core-main-convergence-r1`

CAPT provenance mission: `mission-main-convergence-7f16527a311c`

## Disposition

`IMPLEMENTED_ON_CURRENT_NATIVE_PROVIDER_SPINE_WITH_AUTHORITY_HARDENING`

This checkpoint adds the missing PR #48 bounded Cohort coordination layer, durable UPG-010 Cohort state/evidence admission, and UPG-011 human steering to the current native/provider spine. It does not authorize release or merge to main.

## Missing ancestor recovered

The current PR #107 lineage descends through PR #47/#98/#100 but never inherited PR #48's bounded Cohort coordination module. `capt_runtime.cohort` was absent before this convergence slice.

The verified bounded coordination model is now present with:

- typed contribution identities and outcomes;
- explicit deliberation epoch and round identities;
- participant roster and caps;
- participant cursors over authoritative global sequence;
- stale-epoch handling;
- round-local silence quorum;
- material dissent/escalation/evidence debt;
- explicit bounded-incomplete termination.

## Durable Cohort authority

`CohortAggregate` now owns the durable reconstruction state:

- mission/task binding;
- epoch and round position;
- immutable roster/quorum/cap configuration after creation;
- participant cursors;
- append-only immutable admitted contributions;
- stopping reason;
- evidence links;
- latest human steer.

`GovernedRuntimeService.persist_cohort_snapshot()` atomically commits both:

1. the Cohort stream transition; and
2. the corresponding evidence link on the Claim stream.

A crash cannot leave the Claim pointing at Cohort evidence whose authoritative Cohort state was never persisted.

## Human steering

The one canonical service stack is now:

`RuntimeService -> GovernedRuntimeService -> SteeredRuntimeService`

The composition root selects `SteeredRuntimeService`; no sidecar EventStore or alternate mutation authority is introduced.

The authenticated command relay adds `steer_deliberation`. Only a human actor may invoke the underlying `steer_cohort` authority operation. Steering:

- increments the durable deliberation epoch;
- resets the round position;
- preserves earlier contributions as stale evidence;
- clears prior stopping state;
- records the operator identity, directive, reason, timestamp, and new epoch;
- does not create or widen any capability grant or lease.

The shared Operator facade exposes the same governed command.

## Authority defects found and corrected during convergence

The historical UPG-010 terminal aggregate allowed caller-supplied snapshots to change fields that control deliberation semantics. A cognitive/system caller could therefore have silently changed quorum or imitated steering.

The converged aggregate/service now rejects all of the following:

- changing `required` participants after creation;
- changing roster after creation;
- changing participant or round caps after creation;
- advancing or regressing the epoch through snapshot persistence;
- regressing the round position;
- rewriting or deleting an already admitted contribution;
- forging `latestSteer`;
- injecting caller-supplied evidence IDs;
- seeding steering/evidence authority in an initial snapshot;
- future-epoch contributions;
- future-round contributions in the current epoch;
- a caller-supplied stopping reason that disagrees with deterministic Cohort state.

Only the dedicated human steering transition may change the epoch. RuntimeService evidence admission owns Cohort evidence IDs. The aggregate derives/validates the stopping reason from admitted contributions rather than trusting a cognitive claim of quorum.

## Replay design

Caller-facing aggregate creation/update remains fail-closed for authority-owned fields. Replay uses separate trusted-event reconstruction methods for RuntimeService-authored Cohort events so evidence IDs already minted inside the atomic transaction can be reconstructed without making those fields caller-writable.

`CohortCreated`, `CohortSnapshotPersisted`, and `CohortSteered` are first-class EventEnvelope variants.

The checkpoint contract gains an optional backward-compatible `cohortVersions` field. Cohort state is therefore seeded at its exact checkpoint version rather than being rescanned from ledger origin.

## Verification

RED evidence before implementation:

- the native/provider spine had no `capt_runtime.cohort` module, so bounded Cohort/durability/steering tests failed collection;
- authority-attack tests were written before production hardening for quorum rewrites, epoch forgery, steering forgery, contribution mutation, evidence injection, and stopping-state forgery.

Focused gate after integration:

- Cohort coordination, durability, steering, replay, contracts, approval and promotion interaction: `58 passed`;
- generated-contract drift: PASS;
- TypeScript fixture parity: PASS.

Broad exact working-tree gate:

- Python: `998 passed, 13 skipped, 12 deselected`;
- contract drift: `DRIFT CHECK: OK (11 generated files match the schema source)`;
- Swift: `54 executed, 4 explicit live-runtime skips, 0 failures`;
- `swift build --product CAPTNativeMac`: PASS;
- `git diff --check`: PASS.

## Remaining limits

This is source-tree and native-build proof. Terminal installed-wheel/app and real cross-surface macOS/MCP acceptance remain later convergence gates. Cohort majority/silence is not verification and does not authorize capability expansion, artifact adoption, ClaimGuard acceptance, or task completion.
