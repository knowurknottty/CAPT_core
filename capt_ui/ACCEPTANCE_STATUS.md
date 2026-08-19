# CAPT UI — Acceptance and Classification Status

UI/operator surfaces are thin clients over RuntimeService/EventStore authority.

## Protected `main`

Protected `main` has the established Textual TUI, Tk reference operator surface, shared Operator facade, provider/model configuration foundations, CaveCAPT presentation controls, onboarding, and the older Swift client baseline.

## Terminal convergence candidate — PR #117

The candidate integrates the formerly stacked prompt/provider/cognitive projections plus a real native `CAPTNativeMac` application target. Fresh 2026-08-19 verification establishes:

- Core Python full suite: **1,055 passed / 57 skipped / 12 deselected / 0 failures**;
- Swift normal: **64 / 7 explicit opt-in skips / 0 failures**;
- Swift strict concurrency + warnings-as-errors: **PASS**;
- ThreadSanitizer: **64 / 7 skipped / 0 failures**;
- native `CAPTNativeMac` build: **PASS**;
- MCP PR #2 suite + Ruff against the same Core candidate: **PASS**;
- macOS ↔ RuntimeService ↔ MCP shared-runtime acceptance: **CROSS_SURFACE_PASS**.

Native session state is isolated per chat/session; late async provider/model/approval results target the originating session rather than contaminating the active chat. The native session cache has encrypted storage and private-permission regression coverage.

## Provider/UI coherence

PR #118's provider-selection repair is reconciled onto the candidate. Global provider/model persistence is coherent, legacy provider defaults backfill safely, restored-session provider state remains distinct from New Chat defaults, and the false generic native MLX placeholder is not shown as operational.

## Cohort/UI status

The convergence line includes durable Cohort persistence, evidence admission, governed steering, and Cohort Chamber projection. Cohort majority/quorum remains advisory and cannot manufacture verification or capability.

## Release boundary

The UI/native candidate is integration-verified but **not release-certified**. Security Closure Cockpit authorization, final exact artifacts/hashes, and signed/notarized distribution evidence are separate gates.

Current classification: `IMPLEMENTED_CROSS_SURFACE_VERIFIED_RELEASE_SECURITY_BLOCKED`.
