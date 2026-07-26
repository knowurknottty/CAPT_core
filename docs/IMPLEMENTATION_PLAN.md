# PROPOSED ORDERED IMPLEMENTATION PLAN

**Phase:** 1 — companion deliverable (issue #5 "Immediate deliverables" #4)
**Baseline:** `knowurknottty/CAPT_core` @ `main` `abeff5c`
**Branch:** `integration/full-public-architecture`
**Date:** 2026-07-26

Plan groups work into independently reviewable PRs. Items marked **[OWNER]** require an owner decision before the PR can be opened (per issue stop conditions). This document is inventory/planning only — no runtime behavior changed.

---

## PR-0 — Baseline integrity fix (blocking, no architecture change)
**Goal:** make a fresh clone importable and gates green.
- Commit `capt_solo/ctp/` (restore from wheel `capt_solo/ctp/journal.py` + `__init__.py`) OR adjust `.gitignore` + import strategy. [OWNER: approve committing ctp/]
- Reconcile version: set `pyproject.toml` to `0.4.1`, tag `v0.4.1`. [OWNER: canonical version]
- Re-run `verify_runtime.py` + `pytest`; attach pass output.
- Evidence: import succeeds, 52 verify checks pass, 361 tests pass.

## PR-1 — Memory substrate hardening (capt-solo internal, no external deps)
**Goal:** close partial gaps that need no owner boundary decision.
- P3 Identity model (define table + API) — if owner confirms in-scope.
- P5 cross-module memory coherence check.
- P4 Replay API (or document recovery-only).
- Add unit/integration/negative tests per issue completion standard.

## PR-2 — Port core bioCAPT memory modules [OWNER: public/private boundary + licensing]
**Goal:** bring HMC, ECHO, ENGRAM, DREAM into capt-solo memory layer (or adapter).
- M1 HMC (holographic/FFT VSA) — port + Rust-accel decision.
- M2 ECHO (ring buffer) — port or map to SessionStore.
- M3 ENGRAM — port or fold into consolidation.
- M4 DREAM/consolidation loop.
- Each with migrations, tests (unit/integration/negative/security), docs, verify_runtime checks.

## PR-3 — Proof/trust/knowledge completion [OWNER: security exposure]
- M9 explicit Proof Ledger (if required) atop ProofEngine+governance_audit.
- M10 Skill Radar (fold into SkillFoundry or port).
- IMMU (X3) trust/scoped verification mapping.

## PR-4 — External gateway / sync / consent [OWNER: security exposure + licensing]
- M7 Consent tracking.
- M8 Synchronization (or confirm local-first).
- PULSE (X6) LLM gateway boundary.
- X11 RYS bridge.

## PR-5 — Registry-module triage [OWNER: public/private + metaphorical]
- X1–X14: per-module port/exclude decision (NEDA, QIPC, CONSC, PLAST, CIG, HDR, META, ALLO, FILT/FSR bug-fix, +30 registry, CAPTLANG compiler).
- Each approved module: production impl + tests + docs + verify gate.

## PR-6 — Integration hardening (Phase 5)
- Fault injection, crash recovery, corruption, migration rollback, concurrency, idempotency, replay, privacy, secret-handling, degraded-mode.

## PR-7 — Release readiness (Phase 6)
- README/version/docs, architecture + API references, all release gates, signed evidence report, open PR to `main` (NOT direct merge).

---

## Autonomy boundary
- Autonomous through: PR-0 (after owner approves ctp commit + version), PR-1, and any PR section the owner explicitly marks "approved".
- Stop for owner on every **[OWNER]** gate (public/private boundary, licensing, security exposure, irreconcilable canonical behavior).
- No deletion/renaming of subsystems based on forensic opinion (issue architecture-preservation rules honored).
