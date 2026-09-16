# CAPT Core Roadmap

This roadmap separates merged implementation, exact-source release evidence, merged benchmark/probe source with separate empirical proof, and approved-but-unimplemented product design.

Snapshot date: **2026-09-15**. Reconciled source HEAD: `1e85bac5d17cde342a1ae55e6ee3da5fa681ff61`.

## Historical numbered release — v0.5

Package metadata in `pyproject.toml` remains `capt-solo 0.5.0`. Artifacts preserved under `release_evidence/v0.5/` remain historical evidence for their exact lineage, not authorization for this HEAD.

## Core convergence and terminal tooling — merged

- [x] PR #117: reconcile Discovery, provider/Ouroboros lifecycle, UPG-001→019, native macOS, Cohorts, replay, artifact promotion, provenance/epistemic/security projections, authored-skill approval binding, and MCP shared authority into one Core spine;
- [x] exact historical replay correction and governed replay fork;
- [x] durable Cohort persistence/evidence admission + governed steering + Chamber;
- [x] governed workspace mutation/promotion lifecycle;
- [x] capability lease inspection/revoke and forensic flight bundle;
- [x] first-class Ollama and local/authenticated OpenAI-compatible execution with bounded prewarm;
- [x] native `CAPTNativeMac` chat/operator target and session hardening;
- [x] coherent provider/model persistence and retirement of the false generic native MLX placeholder;
- [x] historical macOS ↔ RuntimeService ↔ MCP shared-ledger acceptance on its recorded snapshot; this is not current-HEAD acceptance;
- [x] PR #126: governed ToolBroker/ToolExecution with initial `local | ssh | docker` terminal backends plus bounded file/code adapters and restart reconciliation;
- [x] PR #129: managed-local Agent Skills import/verify, deterministic contextual selection, exact approval binding, execution anti-drift, and native approval visibility.

## Convergence through September — merged

- **PR #146** — CAPT-UPG-020→024 benchmark/probe and cognitive-debt convergence, merge `cefc885`; empirical effectiveness and provider-cache claims remain separate proof obligations.
- **PR #148** — native macOS control center, Prompt Intelligence proposals/approval binding, and model/tool authority work, merge `5709380`; semantic operator-control API subsequently merged at `42a6cd2`, with revision/digest-bound configuration and prompt selection subordinate to RuntimeService/EventStore.
- **PR #153** — Model Council alpha, merge `542f820`: tier geometry, logical Vessel expansion, launch interlocks, dissent-preserving analysis, durable admission/replay/checkpoints, and read-only Chamber projection; live provider execution, native Council GUI, and release proof remain separate.
- **PR #155** — hardening tiers 1–5, merge `5812a0c`: read projections, mission/DriverRun authority gates, identity-refusal auditing, honest absent-context provenance, and explicit unshipped labels for `context_pipeline` / `context_merkle`.
- **PR #156** — SOMA M0 contract closure, merge `4f1c0a1`: trajectory/reducer contracts, compression receipts, and local benchmark/reconstruction primitives; this does not establish live runtime integration or competition readiness.
- **`d33a5e4`** — native model-answer rendering separated from the execution receipt, with retained disclosure/persistence of execution details.
- **`1e85bac`** — expands AUTO routing signals to include list/match and other actionable requests; the four-word minimum and operator-selected engine/mode still apply. This is routing, not proof of a Search/Deep Research product surface.

## Public-release design authority — merged as documentation

PR #128 preserves the exact owner-approved design from #111 and executable plans from #116 on current Core `main` without importing stale runtime ancestry.

That closes the **design/planning placement** task, not the product implementation itself.

Still to implement/verify from that authority:

- [ ] Secure Intake / Quarantine and hostile-file analysis boundary;
- [ ] Projects and governed project-context eligibility;
- [ ] complete the human-first results layer; native model-answer / execution-details separation is implemented at `d33a5e4`;
- [ ] composer capability palette and explicit precedence;
- [ ] Search / Deep Research governed workload surfaces;
- [ ] complete Council public product integration and live provider proof; Model Council alpha contracts, logical Vessel semantics, replay/checkpoints, and read-only Chamber are merged via #153.

## Release evidence still required for a public artifact cut

The security-closure source `2199c036aa22af33fb3eb0700f63f820a35aa55a` has an exact hosted Release Security PASS receipt. ToolBroker PR #126 exact head `b21ed6e7ff3996d48c756e342b278b69af0d666f` also passed hosted M0-A and Release Security before squash merge.

Those facts do not authorize an arbitrary descendant SHA. For the source actually selected for release:

- [ ] obtain/confirm exact-source M0-A and Release Security PASS;
- [ ] resolve any current CI/environment defect rather than waiving it;
- [ ] rebuild and hash final wheel/sdist/native artifacts from that exact source;
- [ ] verify installed-runtime identity and continuity from those artifacts;
- [ ] complete signing/notarization/distribution/auto-update evidence where applicable;
- [ ] publish only after those release-specific gates close.

Historical August 27 audit: `3aee737…` had a mixed M0-A push run (`32958741310`): Python 3.12, contract drift, and TypeScript parity passed; Python 3.10 failed during the Docker availability probe. A retry was recorded by that audit; no retry outcome or current-HEAD CI result is established here. This is historical evidence, not status for `1e85bac…`.

## CAPT-UPG-020→024 — merged source, remaining proof

CAPT-UPG-020→024 source was reconciled into Core through **PR #146 (`cefc885`)**. The earlier #89/#91/#93/#95/#97 lane is historical implementation lineage, not a list of pending Core merges.

- CAPT-UPG-020: reciprocal-review scorer/harness; empirical effectiveness requires observed trial evidence.
- CAPT-UPG-021: read-only sparse symbol index over Discovery/SEAL-admitted candidates; real-repository performance requires benchmark evidence.
- CAPT-UPG-022: Tree-sitter structural-hash probe; grammar/runtime and semantic-equivalence claims are separate.
- CAPT-UPG-023: chunk-stability/FastCDC probe; chunk reuse does not prove provider prefix-cache reuse.
- CAPT-UPG-024: cognitive-debt projection and `capt-debt` surface; absence of reported debt does not prove correctness.

The source merge is complete; benchmark outcomes and exact-source release verification remain separate obligations.

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
