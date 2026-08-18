# CAPT-UPG-018 — Cohort Deliberation Chamber

- **Campaign ID:** `CAPT-UPG-018`
- **Issue:** #103
- **Base:** verified CAPT-UPG-017 @ `29ff2794884f54479dc0ce4eaf34cd10006479e2`
- **Disposition before exact-commit gate:** `IMPLEMENTED_PENDING_EXACT_COMMIT_VERIFICATION`

## Product boundary

The Chamber is a **projection/control workspace over durable Cohort state**, not a multi-chat simulation and not a cognition authority.

It may display only data actually persisted by CAPT-UPG-010/011:

- cohort / mission / task identity;
- roster and required participants;
- current epoch / round and configured caps;
- participant cursors;
- contribution ID, participant, epoch, round, outcome, cursor, source sequences;
- material dissent flag;
- escalation category;
- authoritative recorded stopping reason;
- Cohort evidence IDs;
- latest durable human steering record.

It deliberately does **not** invent:

- contribution/proposal text not present in Cohort state;
- model/provider identity not present in Cohort state;
- hidden chain-of-thought;
- confidence percentages;
- truth/verification from PASS or quorum;
- capability expansion from steering.

## Shared projection semantics

`capt_ui.operator.cohort_chamber.project_cohort_chamber()` provides one deterministic view for all surfaces.

### Epoch / round truthfulness

Each contribution is classified as one of:

- `stale_epoch`;
- `prior_round_current_epoch`;
- `current_round`;
- `future_round_current_epoch` integrity anomaly.

Only latest current-round contribution state can satisfy current-round required-participant PASS. Old-round PASS and stale-epoch PASS never satisfy current quorum.

A future-round contribution is shown as an integrity warning and excluded from current quorum/debt rather than silently treated as current state.

### Concrete cognitive debt

The Chamber exposes explicit counts only:

- current-epoch material dissent;
- current-epoch escalation;
- current-epoch evidence requests;
- stale-result count.

No opaque scalar or confidence score is produced.

### Silence quorum projection

The display-side projection mirrors the existing bounded Cohort semantics:

- every required participant's latest current-round contribution must be PASS;
- current-epoch material dissent / escalation / evidence-request debt blocks silence quorum;
- on the final permitted round without valid quorum, projected stopping is `BOUNDED_INCOMPLETE`.

The authoritative persisted `stoppingReason` is displayed separately from the recomputed projection. A disagreement is surfaced as `recorded_stopping_reason_differs_from_projection`; the UI never overwrites or disguises the recorded state.

## Shared Operator control

`Operator.cohort_chamber(cohort_id)` reads the authoritative `cohort-<id>` aggregate and applies the pure projection.

Steering reuses the already-governed UPG-011 path:

`Operator.steer_deliberation()` -> authenticated runtime relay -> `SteeredRuntimeService` -> durable `CohortSteered`.

The Chamber adds no new steering authority and cannot widen capability leases.

## Desktop Chamber

`desktop.cohort_chamber` / `capt-cohort` provides:

- deterministic `--headless` JSON projection;
- Tk/Aqua contribution table with epoch/round/outcome/temporal/debt-relevant metadata;
- participant/evidence/latest-steer detail inspector;
- recorded vs projected stopping status and integrity warnings;
- directive + required-reason fields;
- governed steer button and refresh.

## Textual Chamber

`capt_ui.surfaces.tui.cohort_chamber_app` / `capt-cohort-tui` provides:

- same shared deterministic projection text;
- refresh control;
- directive + reason input;
- governed steer button;
- no UI-owned Cohort state.

Textual's in-process harness proves that pressing the steer button submits exactly one `Operator.steer_deliberation()` call with the entered cohort/directive/reason.

## Live durable acceptance observed before commit

A real runtime database was prepared through `GovernedRuntimeService.persist_cohort_snapshot()`, then reopened behind the authenticated socket service.

Before steering:

```text
currentEpoch=1
projectedSilenceQuorum=true
```

After authenticated `steer_deliberation`:

```text
currentEpoch=2
projectedSilenceQuorum=false
prior PASS temporalClass=stale_epoch
latestSteer.directive=inspect alternate evidence
```

This proves the Chamber follows durable EventStore Cohort state rather than maintaining presentation-local deliberation state.

## Pre-commit verification

```text
DRIFT CHECK: OK (11 generated files match the schema source)
focused Chamber projection/operator/surface gate: 13 passed
full non-slow suite: 1011 passed, 13 skipped, 12 deselected
```

## Exact-head / package acceptance required

After commit creation, rerun contract drift, the 13-test focused gate, and the full non-slow suite. Then build/install the wheel and prove:

- `capt-cohort --help`;
- `capt-cohort-tui --help`;
- installed projection/Tk/Textual imports;
- installed `capt-cohort --headless` against an authenticated runtime with real durable Cohort state;
- installed Tk launch smoke on the CAPT-qualified Python 3.12 desktop toolchain.

No claim extends to repository tests excluded by the `slow` marker or to exhaustive visual QA.
