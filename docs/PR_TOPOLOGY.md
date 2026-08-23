# CAPT Core Pull-Request Topology

This is the current routing map for CAPT Core work. PR state, merge state, engineering verification, and release authorization are separate facts.

Snapshot date: **2026-08-23**.

## Merged Core authority

- **PR #117 — terminal native + provider + UPG + MCP convergence**: **MERGED** at merge commit `4a654a74083cf341f8557983ce256949198a02e7`; merged PR head `570babeef113943860c1268722200a48639e406d`.
- **PR #115 — pinned CAPT_Skills authored context**: merged earlier into the Core line.
- **PR #121 — transparent provenance-canary telemetry disclosure**: merged before the final #117 merge-head reconciliation.
- **PR #45 — preserved DeepSeek/Ouroboros research session**: merged after #117 as documentation/archive material; it does not alter runtime authority.
- **PR #124 — release-security gate closure**: merged; release-security implementation baseline `2199c036aa22af33fb3eb0700f63f820a35aa55a`.
- Release-security implementation baseline at this snapshot: `2199c036aa22af33fb3eb0700f63f820a35aa55a`. Resolve literal current `main` from Git; documentation-only merges advance the SHA and must carry their own exact-head CI receipt.

### Release boundary on merged #117

The exact merged #117 head has:

- M0-A Contract & Runtime Proof: **PASS**;
- Native macOS Swift: **PASS**;
- Release Security: **FAIL** — workflow run `32440329043`.

Therefore #117 is merged implementation authority but **not release-authorized**. The prior detailed gate projection at `33e24146094242d7a88612cea39267ef52a1d2e1` recorded `releaseAuthorized=false` with `2 PASS / 0 FAIL / 19 NOT_VERIFIED / 26 NOT_APPLICABLE`; those counts remain bound to that earlier exact head.

PR #124 does not rewrite that history: it adds a newer authorized source state. On the release-security implementation baseline `2199c036aa22af33fb3eb0700f63f820a35aa55a`, Release Security run `32617740908` is **PASS** with **21 PASS / 0 FAIL / 0 NOT_VERIFIED / 26 NOT_APPLICABLE**, and M0-A run `32617740848` is PASS. Current `main` is therefore release-security authorized even though the older #117 exact head remains historically blocked.

## Closed/superseded Core implementation PRs

- **PR #118**: closed unmerged; provider/model-coherence semantics were reconciled into #117 before merge.
- Earlier provider/native/UPG-001→019 implementation PRs closed as superseded remain historical evidence, not competing current authority.

Do not mechanically merge a stale stacked PR merely because its implementation was useful; check whether its semantics already exist on merged `main`.

## Open CAPT-UPG-020→024 lane

These remain separate benchmark/probe/pending-verification work and are **not** part of merged #117 authority:

- **#89 — CAPT-UPG-020** reciprocal-review benchmark harness: `HARNESS_HARDENED_VERIFIED / EMPIRICAL_RUN_PENDING`.
- **#91 — CAPT-UPG-021** sparse symbol-index probe: empirical repository benchmark pending.
- **#93 — CAPT-UPG-022** Tree-sitter structural-hash probe: runtime benchmark pending.
- **#95 — CAPT-UPG-023** FastCDC/content-defined chunk probe: runtime/provider-cache evidence pending.
- **#97 — CAPT-UPG-024** cognitive-debt cockpit: exact-head verification pending.

These should be evaluated/rebased individually against current `main`; their older stacked bases are not by themselves merge authority.

## Open Inversion Labs / Forge edition lane

This is a separate governed edition lineage, not public Core release authority:

- **#104** governed Inversion Labs CAPT edition R1;
- **#108 → #109 → #110 → #112** Forge lexical-evidence hardening stack;
- **#119** current Inversion Labs MTPLX/provider convergence lane.

PR #119 is the newest named edition convergence point. Do not flatten this edition-specific line into Core merely because some provider semantics overlap merged #117.

## Open public-release design/planning lane

- **#111** owner-approved public-release design: design-only authority.
- **#116** executable implementation plans derived from #111: planning-only authority.

Neither PR is runtime implementation. Their older bases should be reconciled against current `main` before implementation or merge decisions.

## Workflow/archive records

- **#99** terminal internal Hermes-replacement review workflow remains a workflow/history artifact unless deliberately updated for current `main`.
- **#45** is already merged archive/research documentation.

## Superseded documentation PR

- **#122** was created before #117 merged and therefore describes #117 as an open terminal candidate. After #117 merged and `main` advanced, #122 became stale/non-mergeable and must not be merged as written. This post-merge reconciliation supersedes it.

## Decision rule

For every PR, ask in order:

1. Is the claimed functionality already on current `main` through #117 or another merge?
2. Is the PR Core runtime work, edition-specific work, benchmark/probe work, design/planning, or archive/workflow material?
3. Does its evidence bind to the PR's exact head, or to an older snapshot?
4. Does merging it preserve current authority/security contracts, or reintroduce stale-base semantics?
5. If the PR is release-related, is there exact-head release authorization rather than merely green engineering tests?

Mergeability is not release authority. A merged commit is not automatically a public release.
