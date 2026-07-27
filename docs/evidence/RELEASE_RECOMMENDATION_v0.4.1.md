# RELEASE_RECOMMENDATION_v0.4.1.md

- **classification**: SAFE PUBLIC RELEASE READY (publication deferred per owner Decision 5)
- **date**: 2026-07-27
- **branch**: `integration/full-public-architecture`
- **HEAD**: `84f2b1b` (engine convergence complete through M8)

## Objective evidence

| Check | Result |
|-------|--------|
| Full test suite | **586 passed** |
| Runtime verification | 46 pass / 0 warn / 0 fail / 0 skip |
| Registry validation | 15 checks, 0 fail, 0 warn |
| Workspace validation | ok: True |
| CLI smoke (workspace status) | exit 0 |
| Wheel build | `capt_solo-0.4.1-py3-none-any.whl` (83 entries) |
| Wheel private-scan | 0 matches (rys/puter/mesh absent) |
| Clean import from wheel | engines + pulse + memory types import OK |
| Doc link check | 0 broken links |
| End-to-end engine workflow | math→physics→invention integration verified |

## Owner decisions applied (ADR-0007)
- D1 research modules public if real (none in tree → documented specs only).
- D2 memory finished + public; HMC/ENGRAM/DREAM stay CAPT_core (reconciled partial).
- D3 Puter KV + mesh sync private (none in tree; excluded by absence + guard test).
- D4 PULSE public/optional/disabled-by-default; RYS private (excluded).
- D5 do NOT publish (local commits only; owner publishes manually).
- D6 MIT approved (LICENSE present; metadata consistent).

## Engine scope (defensible)
- **Mathematics**: safe AST parser (no eval/exec), exact Fraction arithmetic,
  dimensional quantities (7 SI dims), structural-affine linear solving,
  extrema-safe intervals, derivation provenance. 43 tests.
- **Physics**: on math substrate; mechanics/thermo/circuits/waves; explicit
  relation classification; dimensional validation. 14 tests.
- **Invention**: 17-step structured workflow; explainable feasibility; contradiction
  detection; safety gates; revision history; integrates math/physics; no patent
  claims. 8 tests.
- **Memory**: 14-type taxonomy; non-destructive revision; provenance; quarantine;
  DREAM inferred-only boundary. 10 tests.
- **PULSE**: optional, disabled-by-default, no network on import, fails closed.

## Remaining debt (evidence-backed, non-blocking)
- Autobiographical/Semantic dedicated store classes are represented as MemoryType
  values within the unified MemoryRecord model (semantics explicit; separate
  stores optional future work).
- HMC compression ratios are design targets, not verified benchmarks (documented).
- PULSE network path not exercised in tests (disabled/fails-closed behavior tested).
- Security review is static + negative coverage, not a formal audit.

## Publication
NOT published. Owner triggers publication manually (Decision 5). Local commits
and this release-candidate state are complete and verified.
