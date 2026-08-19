# CAPT Core v0.6 — Historical Productization Source of Truth

> **Historical planning record.** This document originally governed the v0.6 productization push. Most P0/P1 usability requirements described here drove work now merged into `main` or superseded by the active integration stack.
>
> For present-tense repository truth use [`CURRENT_STATE.md`](CURRENT_STATE.md), [`CAPABILITY_MATRIX.md`](CAPABILITY_MATRIX.md), [`TUI.md`](TUI.md), and exact source/evidence at the relevant commit.

## Original mission

Make CAPT usable by a normal technically capable operator without requiring knowledge of RuntimeService internals, socket paths, DriverHost plumbing, or the full subsystem vocabulary.

## Outcomes now merged

- canonical Start Here / normal CLI on-ramp;
- five-minute local first success;
- simplified mental model and documentation hierarchy;
- normal start/status/stop/checkpoint/resume/evidence/doctor commands;
- shared operator layer;
- provider/model configuration foundations;
- Textual TUI MVP;
- CaveCAPT presentation controls;
- approval/evidence/runtime visibility;
- onboarding and UI continuity scaffolding.

## Requirements that evolved rather than disappeared

The original plan called for a real governed model mission and true cross-model continuity as flagship proof. Those remain valid acceptance goals, but they now live in the newer stacked integration work rather than in this historical planning document.

Active successors include:

- PR #44 Discovery;
- PR #46 Ouroboros/Hermes lifecycle;
- PR #47 TUI cognition/provenance + ProviderDriver;
- PR #48 Cohorts;
- PR #49 SecurityGate.

## Historical value

This file remains useful as a record of why CAPT shifted from architecture-complete-but-difficult-to-operate toward productized operator surfaces. It is no longer the canonical present-tense implementation plan.

Do not infer current missing capabilities from old unchecked v0.6 boxes without comparing them against `main` and the active stack.