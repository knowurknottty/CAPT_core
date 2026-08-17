# CAPT v0.6/v0.7 — Historical UI/UX Productization Requirements

> **Historical requirements baseline.** This file records the UX direction that produced the shared operator layer, provider/model management foundations, Textual TUI MVP, Tk operator MVP, SwiftUI client contract, onboarding, and CaveCAPT presentation controls.
>
> Present-tense UI state is documented in [`TUI.md`](TUI.md), [`DESKTOP.md`](DESKTOP.md), [`CURRENT_STATE.md`](CURRENT_STATE.md), and [`../capt_ui/ACCEPTANCE_STATUS.md`](../capt_ui/ACCEPTANCE_STATUS.md).

## Invariants that still govern UI work

1. The UI is never a second runtime.
2. RuntimeService/EventStore remain authoritative.
3. Provider destination must be visible as local vs remote/cloud.
4. Human approvals must be explicit for governed actions that require them.
5. Evidence/verification/completion must remain separate concepts.
6. Secret material must not leak into logs/evidence/exported diagnostics.
7. Normal operators should not need socket/token/ledger plumbing.

## What has landed since this plan was written

- shared `capt_ui.operator` contract/facade;
- provider and model management foundations;
- CaveCAPT Minimal/Normal/Detailed/Diagnostic presentation setting;
- Textual TUI MVP with runtime/mission/memory/evidence/provider/approval/log panels;
- governed TUI approve/deny/checkpoint/resume/cancel routing;
- Tk operator MVP;
- SwiftUI projection/client-contract library;
- onboarding and continuity scaffolding.

## Current evolution

PR #47 advances the TUI into a richer cognition/operator cockpit with response modes, requested context budgets, prompt-enhancement engines, explicit review/approval, cognitive provenance, and bounded provider generation.

The dedicated `HERMES_LOCAL_002_COMPLETE` evidence branch further maps/tests the Hermes Agent TUI workspace integration state with no product/state-map blocker, while leaving a destructive rollback E2E gap.

## Still-open product goals

- exact-head installed/live-provider acceptance;
- true process-boundary Model-A -> Model-B continuity;
- native desktop `.app` product and distribution polish;
- provider/model parameter depth and parity;
- stronger memory/context visualization;
- independently demonstrated normal-human end-to-end usability on the final release artifact.

This historical file no longer controls version numbering or present-tense capability claims.