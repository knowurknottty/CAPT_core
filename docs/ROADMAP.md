# CAPT Core Roadmap

This roadmap separates merged implementation, exact-source release evidence, active benchmark/probe work, and approved-but-unimplemented product design.

Snapshot date: **2026-08-27**.

## Historical numbered release — v0.5

Preserved under `release_evidence/v0.5/`. Those artifacts remain historical evidence for that exact lineage.

## Core convergence and terminal tooling — merged

- [x] PR #117: reconcile Discovery, provider/Ouroboros lifecycle, UPG-001→019, native macOS, Cohorts, replay, artifact promotion, provenance/epistemic/security projections, authored-skill approval binding, and MCP shared authority into one Core spine;
- [x] exact historical replay correction and governed replay fork;
- [x] durable Cohort persistence/evidence admission + governed steering + Chamber;
- [x] governed workspace mutation/promotion lifecycle;
- [x] capability lease inspection/revoke and forensic flight bundle;
- [x] first-class Ollama and local/authenticated OpenAI-compatible execution with bounded prewarm;
- [x] native `CAPTNativeMac` chat/operator target and session hardening;
- [x] coherent provider/model persistence and retirement of the false generic native MLX placeholder;
- [x] macOS ↔ RuntimeService ↔ MCP shared-ledger acceptance;
- [x] PR #126: governed ToolBroker/ToolExecution with initial `local | ssh | docker` terminal backends plus bounded file/code adapters and restart reconciliation;
- [x] PR #129: managed-local Agent Skills import/verify, deterministic contextual selection, exact approval binding, execution anti-drift, and native approval visibility.

## Public-release design authority — merged as documentation

PR #128 preserves the exact owner-approved design from #111 and executable plans from #116 on current Core `main` without importing stale runtime ancestry.

That closes the **design/planning placement** task, not the product implementation itself.

Still to implement/verify from that authority:

- [ ] Secure Intake / Quarantine and hostile-file analysis boundary;
- [ ] Projects and governed project-context eligibility;
- [ ] human-first result rendering with raw evidence one interaction away;
- [ ] composer capability palette and explicit precedence;
- [ ] Search / Deep Research governed workload surfaces;
- [ ] Cohort Council public product layer and its bounded Vessel semantics.

## Release evidence still required for a public artifact cut

The security-closure source `2199c036aa22af33fb3eb0700f63f820a35aa55a` has an exact hosted Release Security PASS receipt. ToolBroker PR #126 exact head `b21ed6e7ff3996d48c756e342b278b69af0d666f` also passed hosted M0-A and Release Security before squash merge.

Those facts do not authorize an arbitrary descendant SHA. For the source actually selected for release:

- [ ] obtain/confirm exact-source M0-A and Release Security PASS;
- [ ] resolve any current CI/environment defect rather than waiving it;
- [ ] rebuild and hash final wheel/sdist/native artifacts from that exact source;
- [ ] verify installed-runtime identity and continuity from those artifacts;
- [ ] complete signing/notarization/distribution/auto-update evidence where applicable;
- [ ] publish only after those release-specific gates close.

At the 2026-08-27 audit start, `main` `3aee737…` had a mixed M0-A push run because the Python 3.10 Docker availability probe timed out during collection; Python 3.12, contract drift, and TypeScript parity passed. The failed job was retried during the docs audit and remains a hosted-run fact, not something this roadmap can waive.

## Open CAPT-UPG-020→024 lane

- [ ] **#89 / CAPT-UPG-020** reciprocal-review benchmark: run the empirical campaign before making effectiveness claims;
- [ ] **#91 / CAPT-UPG-021** sparse symbol-index probe: execute real-repository benchmark;
- [ ] **#93 / CAPT-UPG-022** Tree-sitter structural-hash probe: run the required grammar/runtime benchmark;
- [ ] **#95 / CAPT-UPG-023** FastCDC probe: obtain runtime/provider-cache evidence before cache claims;
- [ ] **#97 / CAPT-UPG-024** cognitive-debt cockpit: complete exact-head verification.

These are the current open Core PRs. Reconcile them against current `main` rather than mechanically merging stale ancestry.

## Separate edition / repository lines

- Inversion Labs / Forge remains a separate governed edition/history lineage; its branch-local verification is not Core-main release proof.
- Inversion Eval remains an independent MCP-repository lineage unless deliberately reconciled.

## Later hardening

- governed file-backed authored-skill loading for skills above the current inline contract limit;
- independently rooted/signed audit attestations;
- stronger process/container isolation for write-capable autonomous drivers;
- expanded multi-principal isolation if the threat model moves beyond one trusted local OS user;
- additional paid-provider billing controls and evidence when new providers enter the release profile;
- native MLX execution only when a real adapter exists and is independently verified.

A merge, roadmap checkbox, or green engineering suite is not release authorization.
