# CAPT Core Pull-Request Topology

This document is the current routing map for repository work. It is intentionally separate from implementation evidence: a PR can be open, mergeable, or well-tested without being merged or release-authorized.

Snapshot date: **2026-08-20**.

## Merged protected-main authority

- **PR #115 — Integrate pinned CAPT_Skills authored context**: merged to `main`; authored-skill bytes are provenance-checked, frozen before authoritative mutation, and remain context-only rather than capability authority.
- **PR #121 — route provenance canary through transparent telemetry**: merged to `main`; documentation-only, non-destructive, opt-in telemetry disclosure.
- Runtime/product baseline inspected for this reconciliation: `24cd0a0adea0b54990f94776acd01610590c10c6`. PR #122 is this documentation reconciliation; if this file is being read from `main`, #122 has necessarily advanced the branch commit without changing that runtime/product baseline. Resolve the exact current `main` SHA from Git.

## Terminal CAPT Core convergence

- **PR #117 — terminal native + provider + UPG + MCP convergence candidate**: **OPEN / DRAFT / MERGEABLE / RELEASE-SECURITY BLOCKED**.
- Current head: `33e24146094242d7a88612cea39267ef52a1d2e1` on `integration/capt-core-terminal-convergence-r2`.
- Classification: `IMPLEMENTED_CROSS_SURFACE_VERIFIED_RELEASE_SECURITY_BLOCKED`.
- It semantically reconciles the Core implementation line through **CAPT-UPG-019**, native/provider convergence, authored-skill approval binding, and shared macOS/RuntimeService/MCP authority acceptance.
- It must not merge to protected `main` until the exact-head Security Closure Cockpit returns `releaseAuthorized=true` and final exact-source release artifacts/evidence are rebuilt.

**PR #118** is closed unmerged. Its provider/model-coherence semantics were reconciled into the terminal candidate; it is not a competing release line.

## Open public-release design and implementation planning

- **PR #111** — owner-approved public-release design for Secure Intake/Quarantine, Projects, composer capabilities, Search/Deep Research, and Cohort Council. **Design only.**
- **PR #116** — executable RED→GREEN implementation plans derived from #111. **Planning only; no runtime/native implementation.**

These PRs describe a future public-product tranche and are deliberately separate from PR #117 terminal Core convergence.

## Open CAPT-UPG-020 → 024 work

- **#89 / UPG-020** — reciprocal-review benchmark harness: structurally verified; empirical five-mode campaign evidence still pending.
- **#91 / UPG-021** — sparse symbol-index probe: implementation present; real-repository effectiveness benchmark pending.
- **#93 / UPG-022** — Tree-sitter structural hashing probe: implementation present; live grammar/runtime benchmark pending.
- **#95 / UPG-023** — FastCDC/content-defined chunk benchmark: harness present; real FastCDC/provider-cache evidence pending.
- **#97 / UPG-024** — cognitive-debt cockpit: implementation present; exact-head verification remains pending by its own PR classification.

None of #89/#91/#93/#95/#97 is part of the PR #117 merge authority unless separately reconciled and re-verified.

## Open Inversion Labs / Forge edition lineage

The Inversion Labs edition is a **separate governed edition**, not protected-main Core authority.

- **#104** — governed Inversion Labs CAPT R1, bounded dogfood-ready edition.
- **#108 → #109 → #110 → #112** — stacked Forge lexical-evidence hardening sequence. These are edition-specific evidence-quality refinements, not Core release candidates.
- **#119** — current Inversion Labs MTPLX/provider convergence lane; open and mergeable on the edition branch, with live owner-machine MTPLX proof. It does not alter PR #117 RuntimeService/MCP authority contracts.

Do not collapse these PRs into the Core release status or quote their test totals as PR #117 exact-head evidence.

## Open review / workflow records

- **#45** — preserved DeepSeek Ouroboros research session; archival/review material, no Core implementation mutation.
- **#99** — terminal internal Hermes-replacement review workflow; workflow/documentation, not a release verdict by itself.

## Supersession rule

Older stacked implementation PRs remain valuable historical evidence, but their old heads are not current authority when their semantics have been reconciled into PR #117. Preserve their review history; do not mechanically merge stale bases merely to make the PR list look clean.

For a claim about current CAPT, state which layer it belongs to:

1. **merged protected `main`**;
2. **PR #117 terminal Core candidate**;
3. **separate open upgrade/probe work**;
4. **Inversion Labs edition work**;
5. **planning/design/archive material**.

If that layer is not named, the claim is underspecified.
