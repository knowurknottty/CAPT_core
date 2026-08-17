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

When enhancement is enabled and human verification is required, RUN is locally blocked until the proposal is approved.

The current-run panel also carries cognitive provenance including requested/effective context budget and a prompt-assembly digest.

## Hermes Agent TUI workspace evidence

A dedicated pushed evidence branch, `evidence/hermes-local-002-r6` at HEAD `5c8cbf5ec1dfc0034ba7fa0931e21c88fe0cfc04`, records `HERMES_LOCAL_002_COMPLETE` for the Hermes Agent TUI workspace/state-map exercise. The reported environment used Node `v22.22.2`; system npm `11.14.1` was engine-incompatible, so the faithful workspace run used npm `11.17.0` via `npx`.

Reported results:

- 98 passed / 0 failed / 0 skipped;
- 174 passed / 0 failed / 2 skipped;
- no product or state-map blocker.

Remaining bounded gaps are the lack of a destructive external-provider/tool-kill rollback E2E test, the two skips, and an unrelated macOS case-insensitive contributor-email checkout collision.

This evidence is relevant to the Hermes workspace/TUI integration state; it does not by itself prove every CAPT provider or destructive rollback path.

## What these controls do not do

They do not:

- grant capabilities;
- bypass RuntimeService approval;
- make UI state authoritative;
- turn a prompt proposal into evidence;
- make a provider response verified;
- declare task/mission completion.

## Provider execution status

PR #47 contains the bounded ProviderDriver used by the upgraded run path. Its controlled HTTP tests are meaningful protocol/lifecycle evidence, but the final exact-head live-provider installed-runtime acceptance remains open.

## Current classification

- merged Textual TUI: **SHIPPED MVP on `main`**;
- Hermes local TUI/workspace state map: **`HERMES_LOCAL_002_COMPLETE` on dedicated evidence branch**;
- PR #47 cockpit/provider execution: **IMPLEMENTED IN ACTIVE INTEGRATION, NOT SHIPPED**;
- true real-provider cross-model continuity: **PENDING PROOF**.