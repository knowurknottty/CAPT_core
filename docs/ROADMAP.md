# CAPT Core Roadmap

This roadmap separates merged implementation from release authorization and independent future/product lanes.

## Historical numbered release — v0.5

Preserved under `release_evidence/v0.5/`. Those artifacts remain historical evidence for that exact lineage.

## Core convergence — merged

PR #117 is merged into `main` at merge commit `4a654a74083cf341f8557983ce256949198a02e7`.

- [x] reconcile Discovery and hardened Ouroboros/provider lifecycle into one authority spine;
- [x] reconcile CAPT-UPG-001→019 rather than merging stale stacked bases blindly;
- [x] exact historical replay correction and governed replay fork;
- [x] durable Cohort persistence/evidence admission + governed steering + Chamber;
- [x] governed workspace mutation/promotion lifecycle;
- [x] capability lease inspection/revoke, forensic flight bundle, provenance and epistemic projections;
- [x] first-class local OpenAI-compatible execution and bounded prewarm;
- [x] native `CAPTNativeMac` chat/operator target and session hardening;
- [x] coherent provider/model persistence and retirement of the false generic native MLX placeholder;
- [x] authored-skill bytes bound into exact model-visible approval identity;
- [x] macOS ↔ RuntimeService ↔ MCP shared-ledger acceptance.

## Release gates still open

The exact merged #117 head passed M0-A and Native macOS CI but **failed Release Security**. The merge therefore does not authorize a public release.

- [ ] produce legitimate exact-head evidence for every applicable Security Closure Cockpit control;
- [ ] obtain `releaseAuthorized=true` on the exact release source commit;
- [ ] rebuild and hash final wheel/sdist/native artifacts from that authorized commit;
- [ ] complete signing/notarization/distribution/auto-update evidence where applicable;
- [ ] publish only after those release-specific gates close.

## Explicitly separate work

- [ ] CAPT-UPG-020 reciprocal-review benchmark (#89): empirical campaign evidence pending;
- [ ] CAPT-UPG-021 sparse symbol-index probe (#91): real-repository benchmark pending;
- [ ] CAPT-UPG-022 Tree-sitter structural-hash probe (#93): runtime benchmark pending;
- [ ] CAPT-UPG-023 FastCDC probe (#95): runtime/provider-cache evidence pending;
- [ ] CAPT-UPG-024 cognitive-debt cockpit (#97): exact-head verification remains its own gate;
- [ ] Inversion Labs / Forge edition (#104/#108/#109/#110/#112/#119): maintain independent governed edition lineage;
- [ ] public-release design/plan (#111/#116): execute only from approved authority;
- [ ] Inversion Eval: maintain independent MCP-repository lineage.

## Later hardening/product work

- CAPT-managed encryption for sensitive authoritative persistent state where required by the security profile;
- independently rooted/signed audit attestations;
- stronger process/container isolation for write-capable autonomous drivers;
- explicit paid-service billing caps/alerts and evidence collection;
- native MLX execution only when a real adapter exists and is independently verified;
- multi-principal isolation if/when the threat model expands beyond one trusted local OS user.

A merge, roadmap checkbox, or green engineering suite is not release authorization.
