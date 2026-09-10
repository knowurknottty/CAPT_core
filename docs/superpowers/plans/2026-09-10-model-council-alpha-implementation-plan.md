# CAPT Model Council Alpha Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a governed Model Council alpha with four owner-approved tiers, full logical vessel blasts, evidence/dissent analysis, challenge selection, durable admission, and an operator projection.

**Architecture:** Council is authoritative state above existing Cohorts, not a second runtime. Planning expands all logical Vessels at once and records transport timing separately; external calls remain governed DriverRuns. Deterministic claim analysis precedes any language synthesis.

**Tech Stack:** Python 3.12+, dataclasses/enums, CAPT EventStore/GovernedRuntimeService, pytest, existing operator facade.

**Spec:** `docs/superpowers/specs/2026-09-10-model-council-alpha-design.md`

## Global Constraints

- Small = 2 Cohorts x 3 Vessels; Medium = 4 x 6; Large = 12 x 9.
- Extreme = 24 Cohorts x 18-1000 Vessels, default 18.
- Maximum logical blast = 24,000 Vessels.
- Cohort is provider/model identity; Vessel never chooses another model.
- Entire logical blast exists before transport admission.
- Extreme execution requires explicit digest-bound acknowledgement.
- Majority never creates Verification or ClaimGuard acceptance.
- Council code may not directly bypass existing governed provider/DriverRun paths.

---

### Task 1: Contracts, tiers, digest, and logical blast

**Files:** Create `capt_runtime/council.py`; test `tests/capt_runtime/test_council_alpha.py`.

**Interfaces:** `CouncilTier`, `TierPreset`, `CohortDefinition`, `CouncilDefinition`, `VesselDispatchIntent`, `tier_preset()`, `validate_council()`, `council_digest()`, `build_logical_blast()`.
- [ ] Write tier/cardinality tests including exact 24,000-Vessel structural expansion; run and confirm RED.
- [ ] Implement immutable types, validation, deterministic IDs, canonical digest, and one-shot logical blast; rerun GREEN.
- [ ] Add inheritance and digest-mutation tests; keep provider/model identity Cohort-owned.
- [ ] Commit the independently green contracts slice.

### Task 2: Launch interlocks and timing semantics

**Files:** Modify `capt_runtime/council.py`; test `tests/capt_runtime/test_council_alpha.py`.

**Interfaces:** `CouncilLaunchPreview`, `CouncilLaunchAuthorization`, `authorize_launch()`, `VesselTiming`.

- [ ] Write RED tests proving Extreme rejects absent digest-bound acknowledgement and custom Extreme >432 needs custom-scale acknowledgement.
- [ ] Implement preview counts/token/cost fields without invented pricing and deterministic authorization checks.
- [ ] Write RED tests proving logical dispatch, transport admission, provider start, completion are distinct monotonic timestamps.
- [ ] Implement immutable timing transition helpers and rerun GREEN.
- [ ] Commit the launch-safety slice.

### Task 3: Deterministic epistemic graph and challenge selection

**Files:** Modify `capt_runtime/council.py`; test `tests/capt_runtime/test_council_claims.py`.

**Interfaces:** `ClaimStance`, `ClaimObservation`, `CouncilClaim`, `CouncilDispute`, `CouncilAnalysis`, `analyze_claims()`, `select_challenges()`.

- [ ] Write RED tests for consensus, dissent, minority survival, insufficient evidence, and duplicate-Vessel anti-correlation.
- [ ] Implement deterministic grouping by claim ID and Cohort identity; do not infer verification.
- [ ] Write RED challenge tests for material conflict and high-confidence minority signals.
- [ ] Implement challenge selection with bounded deterministic reasons; rerun GREEN.
- [ ] Commit the epistemic slice.
### Task 4: Durable Council aggregate and governed admission

**Files:** Create `capt_runtime/aggregates/council_state.py`; modify `capt_runtime/governed_service.py`; test `tests/capt_runtime/test_council_durability.py`.

**Interfaces:** `CouncilAggregate`, `GovernedRuntimeService.admit_council_plan()`, `GovernedRuntimeService.record_council_analysis()`.

- [ ] Write RED creation, immutable-topology, idempotency, and restart-load tests.
- [ ] Implement aggregate normalization and immutable topology/digest rules.
- [ ] Add RuntimeService commands that persist plan/analysis through EventStore; never dispatch providers inline.
- [ ] Prove replayed state retains raw analysis and dissent; rerun GREEN.
- [ ] Commit the durability slice.

### Task 5: Council Chamber operator projection

**Files:** Create `capt_ui/operator/council_chamber.py`; test `tests/capt_ui/test_council_chamber.py`; modify operator exports only where required.

**Interfaces:** `CouncilChamberProjection.from_state()` returning topology, blast status, timing counts, consensus/dissent/challenge summary, and launch-interlock state.

- [ ] Write RED projection tests for Small and Extreme sessions.
- [ ] Implement read-only projection; no mutation or provider authority in UI.
- [ ] Prove 24,000-Vessel state is summarized without rendering 24,000 rows by default.
- [ ] Commit the operator slice.

### Task 6: Verification, documentation, and branch publication

**Files:** Update capability/current-state documentation only to claim alpha source state actually proven by tests.

- [ ] Run focused Council tests and the full Python suite.
- [ ] Run compile/import/static checks used by the repository where available.
- [ ] Audit `git diff` for placeholders, unrelated edits, authority bypasses, stale 10/111 limits in current documentation, and accidental provider calls.
- [ ] Commit verified documentation, push `feature/model-council-alpha`, and report exact proof state; do not claim release authorization or live paid-provider proof.