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

Current PR #47 source/editable proof at `4334657a919f74803e65d9b01aa5054d6d7b9a61`:

- 8 approval-security regressions passed;
- 31 focused prompt/provider/TUI/operator tests passed;
- 18 Ouroboros lifecycle tests passed;
- `tests/capt_runtime`: 387 passed / 10 skipped / 12 deselected;
- full repository: 861 passed / 67 skipped / 12 deselected.

Still outside that proof class:

- installed non-editable wheel/live-provider acceptance;
- terminal cumulative-stack acceptance beyond this PR head;
- full restart/process-boundary cross-model continuity;
- destructive external-provider/tool-kill rollback E2E.

## Hermes Agent workspace/TUI metadata — currently unverified

The operator supplied LOCAL-002 metadata for `evidence/hermes-local-002-r6` / `5c8cbf5ec1dfc0034ba7fa0931e21c88fe0cfc04` / `reports/local-evidence/HERMES_AGENT_TUI_WORKSPACE_TESTS_AND_STATE_MAP_8F97AE9_2026-08-17.md`, including `HERMES_LOCAL_002_COMPLETE`, Node/npm details, 98/0/0 focused, 174/0/2 broader, and a no-product/state-map-blocker statement.

Terra could not retrieve the branch, commit, or report from the current GitHub remote/API. Those LOCAL-002 values are therefore **not accepted evidence at this checkpoint**. Historical v0.5 Hermes evidence remains separate and intact. If LOCAL-002 is restored, its claims must be re-read from the repository record before they are promoted back into acceptance status.

## Cross-model continuity

Still **PENDING / NOT CLAIMED** as a true process-boundary release proof. Synthetic model IDs or provider-name switching do not satisfy the flagship claim.

## Current verdict

The merged TUI foundation is real. The active cockpit/provider integration is substantial and near completion. The remaining release gates are integration/live-provider/restart/security evidence gates, not a license to relabel unmerged code as shipped.