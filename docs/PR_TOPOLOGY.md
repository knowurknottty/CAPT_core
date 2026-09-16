# CAPT Core Pull-Request Topology

This is the current routing map for CAPT Core work. PR state, merge target, engineering verification, and release authorization are separate facts.

Snapshot date: **2026-09-15**. Reconciled source HEAD: `1e85bac5d17cde342a1ae55e6ee3da5fa681ff61`.

## Merged Core `main` authority

- **PR #115 — pinned CAPT_Skills authored context**: merged into Core; immutable external skill bytes can be verified and bound into governed model context.
- **PR #117 — terminal native + provider + UPG + MCP convergence**: merged at `4a654a74083cf341f8557983ce256949198a02e7`; merged PR head `570babeef113943860c1268722200a48639e406d`.
- **PR #121 — transparent provenance-canary telemetry disclosure**: merged documentation change.
- **PR #124 — release-security gate closure**: merged; exact authorized baseline `2199c036aa22af33fb3eb0700f63f820a35aa55a`.
- **PR #126 — governed ToolBroker**: merged via squash commit `bcfdff9d43b35b5b192cc998b68ce16cc73b9985`; initial terminal backends are `local | ssh | docker` and ToolExecution remains RuntimeService/EventStore governed.
- **PR #128 — public-release design/plan convergence**: merged documentation authority at `54ac314294fb456cb2d9089615996b31dfeca753`; preserves the approved #111/#116 blobs without importing their stale runtime ancestry.
- **PR #129 — governed native authored skills R1**: merged at `3aee7370bac880aed99ce3c9ecfaa6d9ff48101e`; adds managed-local Agent Skills import/verify, contextual selection, exact approval binding, anti-drift enforcement, and native visibility.
- **PR #45 — preserved DeepSeek/Ouroboros research session**: merged archive/research material; not runtime authority.

- **PR #146** — CAPT-UPG-020→024 benchmark/probe and cognitive-debt convergence, merge `cefc885`; empirical effectiveness and provider-cache claims remain separate proof obligations.
- **PR #148** — native macOS control center, Prompt Intelligence proposals/approval binding, and model/tool authority work, merge `5709380`; semantic operator-control API subsequently merged at `42a6cd2`, with revision/digest-bound configuration and prompt selection subordinate to RuntimeService/EventStore.
- **PR #153** — Model Council alpha, merge `542f820`: tier geometry, logical Vessel expansion, launch interlocks, dissent-preserving analysis, durable admission/replay/checkpoints, and read-only Chamber projection; live provider execution, native Council GUI, and release proof remain separate.
- **PR #155** — hardening tiers 1–5, merge `5812a0c`: read projections, mission/DriverRun authority gates, identity-refusal auditing, honest absent-context provenance, and explicit unshipped labels for `context_pipeline` / `context_merkle`.
- **PR #156** — SOMA M0 contract closure, merge `4f1c0a1`: trajectory/reducer contracts, compression receipts, and local benchmark/reconstruction primitives; this does not establish live runtime integration or competition readiness.
- **`d33a5e4`** — native model-answer rendering separated from the execution receipt, with retained disclosure/persistence of execution details.
- **`1e85bac`** — expands AUTO routing signals to include list/match and other actionable requests; the four-word minimum and operator-selected engine/mode still apply. This is routing, not proof of a Search/Deep Research product surface.

Resolve literal `main` from Git when making a SHA-specific claim. Documentation commits and later feature merges advance the branch and do not inherit old exact-head receipts automatically.

## Release/security evidence routing

Historical evidence remains bound to its source:

- PR #117 exact head `570babe…`: M0-A PASS, Native macOS Swift PASS, Release Security FAIL (run `32440329043`).
- Core release-security closure baseline `2199c036…`: Release Security PASS (run `32617740908`) with **21 PASS / 0 FAIL / 0 NOT_VERIFIED / 26 NOT_APPLICABLE**; M0-A PASS (run `32617740848`).
- ToolBroker PR #126 exact head `b21ed6e7ff3996d48c756e342b278b69af0d666f`: M0-A and Release Security PASS. The squash-merge commit is tree-identical but has a different SHA, so the PR-head receipt is not relabeled.
- Historical August 27 audit: `3aee737…` had a mixed M0-A push run (`32958741310`): Python 3.12, contract drift, and TypeScript parity passed; Python 3.10 failed during the Docker availability probe. A retry was recorded by that audit; no retry outcome or current-HEAD CI result is established here. This is historical evidence, not status for `1e85bac…`.

A merge is source authority, not automatic release authorization. A final public release still needs exact-source evidence plus rebuilt/re-hashed artifacts and any required signing/notarization/distribution proof.

## CAPT-UPG-020→024 — merged convergence

CAPT-UPG-020→024 source was reconciled into Core through **PR #146 (`cefc885`)**. The earlier #89/#91/#93/#95/#97 lane is historical implementation lineage, not a list of pending Core merges.

- CAPT-UPG-020: reciprocal-review scorer/harness; empirical effectiveness requires observed trial evidence.
- CAPT-UPG-021: read-only sparse symbol index over Discovery/SEAL-admitted candidates; real-repository performance requires benchmark evidence.
- CAPT-UPG-022: Tree-sitter structural-hash probe; grammar/runtime and semantic-equivalence claims are separate.
- CAPT-UPG-023: chunk-stability/FastCDC probe; chunk reuse does not prove provider prefix-cache reuse.
- CAPT-UPG-024: cognitive-debt projection and `capt-debt` surface; absence of reported debt does not prove correctness.

## Inversion Labs / Forge edition lineage

The former Labs/Forge PR series is **not an open Core-main lane**.

- #104 is closed unmerged and remains historical evidence for the original governed Labs edition.
- #108/#109/#110/#112 are historical Forge hardening lineage.
- #119 merged into the separate Inversion Labs integration base, not Core `main`.
- later Labs convergence work should continue to preserve the separate edition/runtime identity unless deliberately reconciled into Core through a new review.

Do not cite Labs branch verification as Core-main release proof.

## Public-release design and plans

The original design PR #111 and implementation-plan PR #116 are closed historical review vehicles. Their owner-approved document bytes were preserved onto current Core `main` through merged PR #128.

That merge is **design/planning authority only**. It does not prove implementation of Secure Intake/Quarantine, Projects, the human-first result layer, composer capability palette, Search/Deep Research governance, or the complete Council product. Later source separately implements Model Council alpha (#153) and native answer/receipt separation (`d33a5e4`); actionable research routing (`1e85bac`) does not itself implement Search/Deep Research.

## Closed/superseded records

- **PR #154**: historical SOMA branch lineage superseded by the clean M0 merge #156 (`4f1c0a1`).

- **PR #118**: closed unmerged; useful provider/model-coherence semantics were reconciled into the #117 line before merge.
- **PR #122**: stale pre-#117 documentation reconciliation; superseded by the post-merge docs line.
- **PR #99**: workflow/history artifact unless deliberately refreshed against current `main`.

Earlier provider/native/UPG-001→019 stacked PRs remain historical evidence after semantic convergence. Do not revive a stale branch merely because its original implementation was useful.

## Decision rule

For every PR or branch, ask:

1. What branch is the PR actually targeting: Core `main`, a Labs integration base, a benchmark stack, or a documentation-only base?
2. Is the claimed functionality already present on current `main` through a later semantic merge?
3. Does the cited evidence bind to this exact head/tree, or to an older snapshot?
4. Does the change preserve current RuntimeService/EventStore/governance/security contracts?
5. If release-related, is there exact-source authorization rather than merely green engineering tests?

Mergeability is not release authority, and a branch-local PASS is not proof for a different branch.
