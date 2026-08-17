# CAPT TUI — Textual Operator Console

The TUI is a thin interactive operator surface over CAPT RuntimeService. It is **not** a second runtime.

## Launch merged `main`

```zsh
python -m pip install -e '.[ui]'
capt start
capt-ui dashboard
```

The merged bootstrap resolves the same canonical `runtime.sock` / `runtime.token` layout created by `capt start`.

## Merged TUI MVP

The current `main` TUI exposes:

- runtime health/integrity;
- mission/task state;
- memory/context view;
- provider/model state;
- approval queue;
- evidence/verification/ClaimGuard views;
- logs/operator events;
- governed approve/deny;
- checkpoint/resume/cancel controls;
- CaveCAPT presentation verbosity.

Interactive keypress/operator-routing tests established that governed actions route through the shared Operator facade rather than touching EventStore/SQLite directly.

## Active cockpit upgrade — PR #47

The active integration branch upgrades the run panel with:

| Control | Values / behavior |
|---|---|
| response mode | `MAX`, `SPOCK`, `CAVE CAPT`, `MIN` |
| requested context | 32K–256K in 32K steps |
| enhancement engine | `OFF`, `AUTO`, `OMNI`, `META`, `FORGE`, `SIGMA` |
| human verification | explicit checkbox / approval requirement |
| enhancement flow | `ENHANCE -> REVIEW -> APPROVE -> RUN` |

The prompt enhancer is deterministic and presentation-side. If the request is underspecified, it asks for the missing outcome/success criterion rather than inventing one.

When enhancement is enabled, the transformed proposal must be produced before APPROVE. RUN always requires a durable RuntimeService-backed prompt approval, including when enhancement is `OFF`; the separate human-result-verification preference does not grant execution authority.

The current-run panel also carries cognitive provenance including requested/effective context budget and a prompt-assembly digest.

## Hermes Agent TUI workspace metadata

The operator supplied LOCAL-002 identifiers `evidence/hermes-local-002-r6` / `5c8cbf5ec1dfc0034ba7fa0931e21c88fe0cfc04` / `reports/local-evidence/HERMES_AGENT_TUI_WORKSPACE_TESTS_AND_STATE_MAP_8F97AE9_2026-08-17.md` plus `HERMES_LOCAL_002_COMPLETE`, Node/npm details, 98/0/0 focused, 174/0/2 broader, and no-product/state-map-blocker claims.

Terra could not retrieve the branch, commit, or report from the current GitHub remote/API. Those LOCAL-002 TUI/workspace statements are therefore **currently unverified metadata** and are not part of the accepted TUI evidence ledger. Historical v0.5 Hermes evidence remains separate.

## What these controls do not do

They do not:

- grant capabilities;
- bypass RuntimeService approval;
- make UI state authoritative;
- turn a prompt proposal into evidence;
- make a provider response verified;
- declare task/mission completion.

## Provider execution status

PR #47 contains the bounded ProviderDriver used by the upgraded run path. Exact head `4334657a919f74803e65d9b01aa5054d6d7b9a61` has clean source/editable security, focused, Ouroboros lifecycle, runtime, and full-repository verification. Live-provider and installed-runtime acceptance remain open as separate proof classes.

## Current classification

- merged Textual TUI: **SHIPPED MVP on `main`**;
- Hermes LOCAL-002 TUI/workspace state map: **OPERATOR-SUPPLIED / CURRENTLY UNVERIFIED**;
- PR #47 cockpit/provider execution at `4334657a919f74803e65d9b01aa5054d6d7b9a61`: **EXACT-HEAD SOURCE/EDITABLE VERIFIED, NOT SHIPPED**;
- true real-provider cross-model continuity: **PENDING PROOF**.