# RELEASE_STATE.md — Release Readiness

- **package**: `capt-solo`
- **declared version**: `0.4.1` (pyproject.toml)
- **license**: MIT (declared in pyproject). LICENSE file: **added this session** (was missing — a release blocker).
- **release target**: `CAPT_core` public release.
- **last full test run**: `463 passed` (this session).
- **last runtime verify**: `46 pass / 0 warn / 0 fail / 0 skip`.
- **last registry validate**: `15 checks, 0 fail, 0 warn`.
- **release gates (from RELEASE_AUDIT_v0.4, re-verified this session where possible)**:
  - Migration safety, idempotency, abort-on-failure: covered by `tests/test_v04_migration.py` (still green).
  - Bubble manifest v2 / 12-step validation: green.
  - Degradation 12 codes / ClaimGuard scoped language: green.
  - Skill/capability lifecycle: green.
  - SQL boundary audit: green.
  - Plugin 46 tools: `plugin.json` version `0.4.1`, 46 tools (confirmed).
  - Coverage: historically 84%; being re-measured this session.
- **open release blockers (evidence-backed)**:
  1. LICENSE file missing → **resolved this session** (MIT LICENSE created).
  2. Version identity drift (README v0.1 / docs v0.4.0 / pyproject 0.4.1) → **in progress** (TASK-201).
  3. Stale release docs (355/45 vs 463/46) → **in progress** (TASK-202); will add fresh `docs/evidence/UNIVERSAL_WORKSPACE_IMPLEMENTATION.md` and update RELEASE_AUDIT.
  4. I-15 absent from CAPT_CANON table → **resolved this session** (TASK-203).
  5. Universal Workspace layer absent → **resolved this session** (TASK-100).
- **owner gates for public release (require owner, not steward)**:
  - [B] public/private boundary for research_package modules (FILT/FSR/NEDA/ALLO/OUROBOROS).
  - [S] privacy review for Consent/Sync transports.
  - [B]+[S] PULSE/RYS network gateways (safe abstract contracts only; not in core).
- **recommended release decision**: **CONDITIONAL GO** once TASK-201/202 land and the [B]/[S] owner gates are resolved. The codebase itself is internally consistent, proof-governed, migration-safe, and tested. The remaining items are documentation/version hygiene + owner boundary decisions, not code defects.
