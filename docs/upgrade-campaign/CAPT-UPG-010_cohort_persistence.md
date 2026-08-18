# CAPT-UPG-010 — Durable Cohort EventStore Persistence & Evidence Admission

- **Campaign ID:** `CAPT-UPG-010`
- **Issue:** #69
- **PR:** #70
- **Rebuilt Base:** `upgrade/capt-upg-009-workspace-promotion` @ `24e613f4f982fb72ff9bdd92b63ae50377eca90e`
- **Status:** `IMPLEMENTED_PENDING_EXACT_HEAD_TEST`

## Corrected implementation

This revision replaces the earlier evidence-only approximation with an authoritative durable Cohort substrate:

- `CohortAggregate` owns durable cohort identity, mission/task binding, epoch, round, roster, required participants, participant cursors, contributions, stopping state, evidence links, and latest steering metadata.
- `GovernedRuntimeService.persist_cohort_snapshot()` commits the `cohort-<id>` state update and the linked Claim `EvidenceRecorded` event in one EventStore command transaction.
- Evidence IDs are deterministic per Cohort stream version (`ev-cohort-<id>-vN`).
- Contribution deletion, identity rebinding, epoch regression, and participant cursor regression fail closed.
- `full_replay()` and checkpoint-extension replay understand Cohort create/snapshot/steer events.
- `load_cohort_state()` reconstructs typed `BoundedCohort` + `DeliberationEpoch` from authoritative EventStore state after reopen.

## Discriminating tests added

`tests/capt_runtime/test_cohort_durability.py` proves:

1. Cohort state and claim evidence are committed, store closes, SQLite reopens, and typed Cohort state reconstructs.
2. Full replay reconstructs the same `cohort-<id>` authoritative state.
3. Deliberation can continue after restart without contribution loss or duplicate evidence admission.
4. Exact retry is idempotent.
5. Contribution deletion and cursor regression fail closed.

## Exact-head verification required

Run at the terminal PR head:

```bash
pytest tests/capt_runtime/test_cohort.py tests/capt_runtime/test_cohort_durability.py
pytest tests/capt_runtime/test_governed_artifact_promotion.py tests/capt_runtime/test_artifact_workspace.py
pytest
```

Do not promote this item to `IMPLEMENTED_VERIFIED_READY_FOR_OWNER_REVIEW` until exact-head execution evidence exists.
