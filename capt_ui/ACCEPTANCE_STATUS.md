# CAPT UI — Acceptance and Classification Status

UI/operator surfaces are thin clients over RuntimeService/EventStore authority.

## Merged source — 2026-09-15

At `1e85bac5d17cde342a1ae55e6ee3da5fa681ff61`, PR #117 and later work are merged: Textual TUI, Tk reference surface, shared Operator facade, real native `CAPTNativeMac`, governed Settings/Skills/model/filesystem/shell/provider controls, prompt proposals/intelligence, and the native/TUI golden authority tranche. The semantic operator-control API provides revisioned coordination; runtime read projections expose approvals, missions, tasks, and checkpoints.

Model Council alpha (PR #153) includes durable state and Chamber projection. UPG-020–024 (PR #146) includes probes/benchmarks and the cognitive-debt surface. These merges do not establish live-provider quality, achieved Council concurrency, or full product-plan completion.

Native model answers and execution receipts are separated by `d33a5e4`; `1e85bac` expands AUTO action signals, including list/match, subject to the four-word minimum and operator-selected engine/mode. That routing is not a Search/Deep Research product completion claim.

## Historical convergence acceptance — PR #117

The 2026-08-19 convergence record reports the following; these are historical results, not fresh verification of the 2026-09-15 HEAD:

- Core Python full suite: **1,055 passed / 57 skipped / 12 deselected / 0 failures**;
- Swift normal: **64 / 7 explicit opt-in skips / 0 failures**;
- Swift strict concurrency + warnings-as-errors: **PASS**;
- ThreadSanitizer: **64 / 7 skipped / 0 failures**;
- native `CAPTNativeMac` build: **PASS**;
- MCP PR #2 suite + Ruff against the same Core candidate: **PASS**;
- macOS ↔ RuntimeService ↔ MCP shared-runtime acceptance: **CROSS_SURFACE_PASS**.

Native session state is isolated per chat/session; late async provider/model/approval results target the originating session rather than contaminating the active chat. The native session cache has encrypted storage and private-permission regression coverage.

## Provider/UI coherence

PR #118's provider-selection repair is reconciled into merged PR #117 (PR #118 itself closed unmerged). Global provider/model persistence is coherent, legacy provider defaults backfill safely, restored-session provider state remains distinct from New Chat defaults, and the false generic native MLX placeholder is not shown as operational.

## Cohort/UI status

The convergence line includes durable Cohort persistence, evidence admission, governed steering, and Cohort Chamber projection. Cohort majority/quorum remains advisory and cannot manufacture verification or capability.

## Release boundary

Merged UI/native source has historical integration evidence but is **not release-certified by that evidence**. Security Closure Cockpit authorization, final exact artifacts/hashes, and signed/notarized distribution evidence are separate gates.

Current source classification: **MERGED SOURCE** with historical integration evidence. Historical cross-surface acceptance does not establish fresh current-HEAD integration, live-provider quality, or release authorization.
