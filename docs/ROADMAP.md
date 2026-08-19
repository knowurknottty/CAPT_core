# CAPT Core Roadmap

This roadmap separates the numbered package release, merged productization work, active integration, and later product hardening.

## Historical numbered release — v0.5

Preserved under `release_evidence/v0.5/`: installed local runtime lifecycle, EventStore/checkpoint/recovery, memory/governance/evidence foundations, bounded Hermes interaction, and associated hosted/local evidence.

## Merged productization foundation

Completed on `main` beyond the original v0.5 experience:

- [x] normal `capt` lifecycle/on-ramp;
- [x] shared operator facade;
- [x] provider registry/health/model-list foundations;
- [x] model-selection/favorites/override foundations;
- [x] CaveCAPT presentation verbosity;
- [x] Textual TUI MVP;
- [x] governed TUI approval/control path;
- [x] Tk operator MVP;
- [x] SwiftUI client-contract library;
- [x] onboarding/UI continuity scaffolding.

## Active integration stack

- [ ] **#44 Discovery** — merge bounded Discovery Governor/SEAL scanning.
- [ ] **#46 Ouroboros/Hermes lifecycle** — merge hardened dispatch/idempotency/lease/recovery semantics.
- [ ] **#47 TUI cognition + ProviderDriver** — merge prompt assembly/provenance, cockpit controls, and bounded Ollama/OpenAI-compatible generation; exact source/editable head `4334657a919f74803e65d9b01aa5054d6d7b9a61` is full-suite verified, while installed/live-provider proof remains separate.
- [ ] **#48 Cohorts** — merge bounded coordination contracts while keeping durable claims deferred.
- [ ] **#49 SecurityGate** — close applicable controls with exact-head evidence; remain blocked until then.

## Hermes LOCAL-002 evidence checkpoint

- [ ] restore/publish an independently retrievable LOCAL-002 branch/commit/report if this evidence record is intended to remain part of the public ledger;
- [ ] independently verify the **currently unverified** operator-supplied `evidence/hermes-local-002-r6` / `5c8cbf5ec1dfc0034ba7fa0931e21c88fe0cfc04` metadata and the reported 98/0/0, 174/0/2, skip, npm, and no-blocker claims before promoting them back to evidence;
- [ ] destructive external-provider/tool-kill rollback E2E remains separately unproven regardless of LOCAL-002 restoration.

## Release-critical acceptance still open

- [ ] exact terminal stacked-head full integration acceptance;
- [ ] installed-runtime/live-provider acceptance for intended provider paths;
- [ ] true Model A -> shutdown/restart -> Model B no-repeat continuity proof;
- [ ] durable Cohort persistence/reconstruction/evidence admission before durable Cohort claims;
- [ ] security closure for all applicable #49 controls;
- [ ] native desktop application product beyond Tk MVP / SwiftUI library.

## Later hardening/product work

- native desktop packaging/signing/notarization/auto-update;
- MLX/mlx_lm native execution parity;
- stronger provider parameter/resource controls;
- encrypted state/export options;
- signed attestations/audit roots;
- stronger process isolation;
- platform expansion including separately proven Windows support;
- durable/distributed coordination only where a real use case justifies it.

A roadmap checkbox is not release evidence.