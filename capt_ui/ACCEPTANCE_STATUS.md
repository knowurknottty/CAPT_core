# CAPT UI — Acceptance and Classification Status

This document distinguishes merged UI capability, active integration, and release proof.

## Merged operator foundation

- **Textual TUI MVP:** merged and usable for runtime/mission/memory/evidence/provider/approval/log views and governed operator controls.
- **Shared Operator facade:** merged; UI does not write EventStore/SQLite directly.
- **Provider manager:** merged registration/configuration plus health/model discovery where supported.
- **Model manager:** merged model-selection/favorites/defaults/override foundation.
- **CaveCAPT verbosity:** merged and presentational only.
- **Tk desktop:** operator MVP/reference fallback, not native product.
- **SwiftUI:** client-contract library, not a shipped `.app`.

## Provider support boundary on `main`

Provider registration/health/model-list support does **not** equal governed generation. `main` does not yet ship the PR #47 ProviderDriver.

## Active PR #47 acceptance state

Implemented in the active stacked branch:

- deterministic prompt assembly;
- cognitive provenance envelope;
- requested/effective context accounting;
- TUI response-mode/context/enhancement/human-review controls;
- bounded ProviderDriver for Ollama native and OpenAI-compatible generation;
- protocol/lifecycle/provenance/secret-handling tests against controlled HTTP servers.

Still outside the focused PR proof:

- exact terminal stacked-head acceptance;
- installed-wheel/live-provider acceptance;
- full restart/process-boundary cross-model continuity.

## Hermes Agent workspace/TUI evidence

`HERMES_LOCAL_002_COMPLETE` is recorded on pushed branch `evidence/hermes-local-002-r6`, HEAD `5c8cbf5ec1dfc0034ba7fa0931e21c88fe0cfc04`, report `reports/local-evidence/HERMES_AGENT_TUI_WORKSPACE_TESTS_AND_STATE_MAP_8F97AE9_2026-08-17.md`.

Reported:

- Node `v22.22.2`;
- system npm `11.14.1` engine-incompatible;
- faithful workspace npm `11.17.0` via `npx`;
- 98 passed / 0 failed / 0 skipped;
- 174 passed / 0 failed / 2 skipped;
- no product/state-map blocker.

Remaining bounded gaps: destructive external-provider/tool-kill rollback E2E unproven; two pytest skips; unrelated macOS case-insensitive contributor-email checkout collision.

## Cross-model continuity

Still **PENDING / NOT CLAIMED** as a true process-boundary release proof. Synthetic model IDs or provider-name switching do not satisfy the flagship claim.

## Current verdict

The merged TUI foundation is real. The active cockpit/provider integration is substantial and near completion. The remaining release gates are integration/live-provider/restart/security evidence gates, not a license to relabel unmerged code as shipped.