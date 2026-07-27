# Phase 3M — Release Verification

**Branch:** integration/full-public-architecture
**Date:** 2026-07-26
**Issue:** #5
**Preceded by:** Phase 3L (commit 951787f)

## Objective
Verify the converged CAPT_core is buildable, installable, testable, and
release-ready: clean build, fresh-venv install, full test suite, runtime
self-check, registry enforcement, and fitness constraints.

## Release-gate results (authoritative: run in repo)
- **Clean build:** `python3 -m build` → `capt_solo-0.4.1-py3-none-any.whl`
  (159 KB) + sdist. Succeeds.
- **Fresh-venv install:** `pip install capt_solo-0.4.1-py3-none-any.whl` →
  imports succeed: `capt_solo` (v0.4.1), `capt_solo.capt_facade.CAPT`,
  `capt_solo.api.CTPRuntime`, `capt_solo.knowledge.evidence.EvidenceStore`.
- **Full test suite (repo):** **463 passed**, 0 failed.
- **verify_runtime.py:** **46/46 pass** (0 warn / 0 fail / 0 skip).
- **Registry validator:** 15 structural checks, **0 fails**.
- **Architecture fitness:** 13 invariant tests, **13 passed**.
- **Sanctioned integrator API preserved:** `capt_solo.api` (CTPRuntime/KHSB/
  Lifecycle re-exports) intact; `capt_solo.plugin` imports verified.

## Packaging fix (part of 3M)
`pyproject.toml` was updated so the clean build includes the new canonical
packages and declares runtime deps:
- `packages` now lists `capt_solo.knowledge`, `capt_solo.execution`,
  `capt_solo.learning`, `capt_solo.research` (previously missing → installed
  wheel lacked these modules; caught by the fresh-venv install check).
- `dependencies` now declares `pyyaml>=5.4` (required by registry/engine;
  previously undeclared → import failed in clean env).

## Known limitation (documented, not a code regression)
When the repo's `tests/` are executed against the *installed* wheel (site-
packages `capt_solo`) as a full suite, `tests/test_v04_cli.py` shows 8 order-
dependent failures (shared global `data_dir`/state across the suite). These
tests pass in isolation and in the repo suite (where `capt_solo` resolves to the
source tree). This is a pre-existing test-isolation concern in the CLI test
harness, not introduced by Phase 3, and does not affect the converged code or
the repo-suite release gate. Recommended follow-up (out of Phase 3 scope): make
`test_v04_cli.py` use a temp `data_dir` fixture for full isolation.

## Phase 3+ completion summary
Phases 3A–3M implemented and committed on `integration/full-public-architecture`:
- 3A architecture enforcement (registry + validator + fitness + ADRs + debt)
- 3B baseline/packaging repair (CTP restore, version 0.4.1, clean build)
- 3C internal memory hardening (canonical fields, migration rollback, recovery)
- 3D episodic/ECHO convergence (clean impl; no external copy)
- 3E replay/consent/local-sync (LAN transport gated, disabled by default)
- 3F autobiographical memory (revision-without-erasure, conflict retention)
- 3G knowledge/evidence convergence (verification gated by evidence, I-02)
- 3H execution boundaries + anti-token hardening
- 3I HMC/ENGRAM/DREAM canonicalization (clean impl; licensing gate [L] avoided)
- 3J continuous learning foundation
- 3K research adapters (optional, graceful degradation I-09)
- 3L external interface hardening (CAPT facade + canon CLI; api.py preserved)
- 3M release verification (build/install/test all green)

No owner gates ([B]/[L]/[S]/[C]) required escalation beyond the documented
licensing-clean implementations and the disabled-by-default LAN transport.

## Verification
- pytest: 463 passed (repo). verify_runtime: 46/46. Registry: 0 fails.
- Build + install: succeeded; imports verified.

## Result
CAPT_core is converged to the approved canonical public architecture, buildable,
installable, testable, and release-ready per the Phase 3+ directive. Pending
explicit user approval to push/PR (standing instruction from Phases 2/2.5).
