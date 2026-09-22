# CAPT MoA Explore → Converge → Enhance → Handoff

## Purpose

Use expensive multi-model orchestration where it has the highest information
value: architecture search, adversarial review, planning, and novel ideation.
Use a cheaper coding model for high-volume implementation after CAPT freezes a
machine-actionable contract.

The council does not become the authority plane. CAPT owns source identity,
contract identity, write authority, verification, reconciliation, and completion.

## Phase 0 — CAPT bind and participation gate

Before council work:

1. bind exact repo/worktree/HEAD or frozen diff digest;
2. bind evidence and current test state;
3. enumerate the expected council topology;
4. prove every configured reference model actually participates;
5. record degraded or missing references explicitly;
6. keep the planning worktree read-only.

If a required reference is absent, do not silently call the result a full council.

## Phase 1 — MoA Explore

Every reference model independently receives the same:

- problem statement;
- architecture and relevant source;
- evidence;
- constraints;
- current state digest;
- non-negotiable invariants.

Each reference returns structured findings:

- weaknesses;
- candidate solutions;
- risks/failure modes;
- evidence IDs/source paths;
- assumptions;
- unresolved questions.

No reference sees or edits another reference's finding before the independent pass
is complete. The aggregator must retain source identity.

## Phase 2 — MoA Converge

The aggregator adjudicates each material recommendation as:

- ACCEPT;
- REVISE;
- REJECT;
- DEFER.

Dissent is retained, not averaged away.

The required output is an implementation contract, not a narrative essay.

The contract must contain:

- exact files/components;
- schemas/APIs;
- invariants;
- migration rules;
- tests and golden vectors;
- prohibited changes;
- rollback strategy;
- unresolved questions;
- verification gates;
- accepted council decision IDs;
- dissent summary.

CAPT computes and freezes the contract digest.

## Phase 3 — Enhancement / upgrade / novelty pass

Only after the core contract is coherent, the council performs a separate search
for:

- enhancements to the accepted design;
- upgrades that materially improve quality, safety, speed, cost, or maintainability;
- novel additions that create genuinely new capability.

Each proposal must state value, risk, dependencies, evidence/assumptions, and
whether it is ACCEPT / REVISE / REJECT / DEFER.

Novelty never silently expands the required implementation scope.

## Phase 4 — CAPT freeze and coder handoff

CAPT freezes:

- source-state digest;
- planning-bundle digest;
- implementation-contract digest;
- accepted enhancement subset;
- write scope;
- test/verification gates.

The cheap coding model receives the frozen handoff, not the council transcript.

The coder may implement and test but may not reinterpret architecture merely from
preference. If it encounters a contradiction or missing requirement, it records a
blocker against the contract.

## Phase 5 — CAPT verification loop

For each bounded tranche:

compile → focused tests → contract tests → diff hygiene

Then:

- continue mechanically when green;
- reconcile when transport/effect state is uncertain;
- return to council only for architectural ambiguity or high-value adversarial review.

## Phase 6 — Targeted council review

At major checkpoints, provide the council:

- frozen implementation contract;
- current diff;
- new/changed tests;
- verification results;
- explicit deviations.

Ask only:

- what violated the contract;
- what the original plan missed;
- whether tests are tautological or incomplete;
- whether a simpler or safer architecture is now evident;
- whether any accepted enhancement should be promoted or deferred.

CAPT records the resulting contract amendment with a new digest before the coder
continues.

## Phase 7 — Completion

The coding model never declares the mission complete by prose alone.

CAPT closes only after the required verification gates, provenance/effect evidence,
and final state digest are satisfied.

## Economic rule

Spend expensive intelligence on high-information decisions.
Spend cheap intelligence on high-volume execution.

Preferred flow:

MoA Explore → MoA Converge → MoA Enhance → CAPT Freeze → Cheap Coder →
CAPT Verify → Targeted MoA Review → Cheap Coder Corrections → CAPT Final

This preserves the council's comparative advantage without making conversational
state responsible for durable implementation progress.

