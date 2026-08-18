# CAPT-UPG-010 — Durable Cohort EventStore Persistence & Evidence Admission

- **Campaign ID:** `CAPT-UPG-010`
- **Issue:** #69
- **PR:** #70
- **Base:** `upgrade/capt-upg-009-workspace-promotion` @ `98734f9e72910ff2a43c3c81cca2dc872e07a993`
- **Disposition:** `IMPLEMENTED_VERIFIED_READY_FOR_OWNER_REVIEW`

## Authoritative implementation

This revision replaces the earlier evidence-only approximation with a durable Cohort substrate:

- `CohortAggregate` owns Cohort epoch/round state, roster/required participants, participant cursors, admitted contribution records, stopping state, evidence links, and steering metadata; mission/task/cohort identifiers remain references.
- `GovernedRuntimeService.persist_cohort_snapshot()` commits `cohort-<id>` state and linked Claim `EvidenceRecorded` admission in one EventStore command transaction.
- Evidence IDs are deterministic per Cohort stream version (`ev-cohort-<id>-vN`).
- Contribution deletion, identity rebinding, epoch regression, non-admitted cursor identities, negative cursors, contribution-order cursor regression, and declared cursor rollback fail closed.
- Declared participant cursor summaries are validated separately from historical contribution cursors; valid old contributions are not incorrectly compared against the already-aggregated latest cursor.
- Full replay and checkpoint-extension replay reconstruct Cohort state.
- `load_cohort_state()` reconstructs typed `BoundedCohort` + `DeliberationEpoch` after SQLite close/reopen.

## Contract integration

The normative EventEnvelope contract now explicitly supports:

- `cohort-*` stream IDs;
- `CohortCreated`;
- `CohortSnapshotPersisted`;
- typed `CohortSnapshot` / contribution / stopping-state structures.

`CohortSteered` is intentionally not admitted at this layer; that authoritative event is introduced by CAPT-UPG-011.

Cross-language fixtures include a valid `CohortCreated` envelope, and the TypeScript parity runner rebuilds current generated source before validation so stale `dist/` output cannot mask schema drift.

## Verification

Focused pre-commit gate on the final UPG-009 ancestry:

```text
DRIFT CHECK: OK (11 generated files match the schema source)
32 passed
```

Exact-commit full-suite verification is required immediately after this manifest/code commit and is recorded on PR #70. Scope excludes slow tests by the repository's configured pytest marker policy.
