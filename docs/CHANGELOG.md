# CAPT Core Changelog

## Unreleased / repository `main` and active integration — 2026-08-17

This section intentionally distinguishes merged `main` from open stacked integration.

### Merged since the original v0.5 package release

- normal `capt` start/status/stop/checkpoint/resume/evidence/doctor on-ramp;
- durable memory CLI;
- shared `capt_ui.operator` layer;
- provider registry/health/model-list foundations;
- model-selection/favorites/override foundations;
- CaveCAPT presentation verbosity;
- Textual TUI MVP with governed approvals/control;
- Tk operator MVP;
- SwiftUI client-contract library;
- onboarding/UI continuity scaffolding.

Package metadata remains `0.5.0`; these merged changes have not yet been represented by a new numbered package release.

### Active stacked integration

- PR #44: bounded Discovery Governor/SEAL scanner;
- PR #46: Ouroboros/Hermes lifecycle and recovery hardening;
- PR #47: prompt assembly/cognitive provenance, TUI cockpit, bounded ProviderDriver;
- PR #48: bounded Cohort coordination;
- PR #49: fail-closed security gate, intentionally blocked pending closure evidence.

### Evidence

- `HERMES_LOCAL_002_COMPLETE` pushed on `evidence/hermes-local-002-r6` at `5c8cbf5ec1dfc0034ba7fa0931e21c88fe0cfc04`;
- reported 98 passed / 0 failed / 0 skipped focused;
- reported 174 passed / 0 failed / 2 skipped broader;
- no product/state-map blocker;
- destructive external-provider/tool-kill rollback E2E remains unproven.

## v0.5.0 — Standalone governed runtime release lineage

The preserved `release_evidence/v0.5/` record is the authority for the exact numbered-release proof and limitations.

## v0.4.1 — Anti-Token-Extraction optional component

Historical addition of the bounded optional anti-token-extraction integration, provenance/degradation controls, and associated tests/docs.

## v0.4.0 — Proof-governed subsystem expansion

Historical addition of Foundry, Proof Engine, Capability Registry lifecycle, ClaimGuard, Knowledge Bubble quarantine/validation, workflow proof, migration safety, governance, and supporting CLI/tests.

## v0.3 / v0.2 / v0.1

Historical development of lifecycle/session/procedure/prospective-memory, KHSB/CTP/retrieval feedback, and the original local memory/core/plugin scaffold.

Historical exact test counts and implementation details should be read from the corresponding committed evidence rather than treated as current `main` claims.