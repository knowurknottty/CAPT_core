# Changelog

All notable changes to CAPT Solo are documented here. This project adheres to
semantic versioning. The current unreleased public candidate is **v0.5.0**.

## [0.5.0] — Unreleased (ContextPack v1 public contract)

### Added
- `capt_solo.contextpack`: a versioned, deterministic ContextPack v1 exchange
  format with canonical JSON, digest verification, protected facts, explicit
  assumptions, AntiToken generation gating, and handoff/resume artifacts.

### Fixed
- Checkpoint mission identifiers are now filename-safe, preventing path traversal
  outside the local checkpoint store.

### Packaging
- Package metadata now uses the SPDX `MIT` license expression; the obsolete
  license classifier/table metadata was removed.

## [0.4.2] — 2026-07-27 (governed evidence + invalidation + workspace isolation)

Adds the Evidence Engine layer on top of the Verified State Identity (VSI)
subsystem. Implements the long-horizon engineering pass: proof-preserving
evidence reuse, first-class invalidation events, project workspace isolation,
scoped memory-promotion boundaries, self-modification governance, mission
checkpoint/restart recovery, long-session efficiency controls, and a structured
guard decision contract.

### Added
- `capt_solo/evidence/core.py`: `EvidenceRecord`/`EvidenceClaim`/`EvidenceSource`/
  `EvidenceClass` (12 classes)/`EvidenceStatus` (8 statuses)/`EvidenceScope`/
  `EvidenceRelation`/`EvidenceBundle`/`EvidenceQuery`/`EvidenceDecision`. Explicit
  separation of present/believed/inferred/attempted/changed/verified/valid/
  invalidated/project-local/globally-reusable — no collapse into one field.
- `capt_solo/evidence/invalidation.py`: `InvalidationEvent`/`Reason`/`Rule`/
  `Scope`/`Decision`/`Graph`. Scoped invalidation (path-based changes affect only
  overlapping evidence; HEAD/lockfile/env/policy are FULL-scope global
  invalidators). Transitive closure supported.
- `capt_solo/evidence/reuse.py`: `EvidenceReuseEngine` — deterministic reuse vs
  re-verification. Repeated equivalent state => reuse, no rerun, no false
  confidence increase.
- `capt_solo/evidence/proof_graph.py`: indexed claim/evidence/verification/
  invalidation graph with BFS traversal + cycle protection.
- `capt_solo/evidence/workspace_isolation.py`: `ProjectWorkspace`/`ProjectContext`.
  Bounded `.capt/` boundary; rejects traversal + symlink escape; unbound workspace
  blocks all project/global persistence; global writes never implicit.
- `capt_solo/evidence/promotion.py`: `PromotionPipeline` (workspace -> candidate ->
  quarantine/validate -> explicit project/global promotion). Forbidden content
  auto-quarantined; inferred/synthetic quarantined until corroborated.
- `capt_solo/evidence/selfmod.py`: `SelfModificationGovernor` with full lifecycle,
  dedup (anti-loop), per-mission cap, global-policy quarantine + external approval,
  mandatory rollback path.
- `capt_solo/evidence/checkpoint.py`: `MissionCheckpoint`/`CheckpointStore`/
  `detect_divergence`/`resume_plan`. Completed missions are not restarted.
- `capt_solo/evidence/metrics.py`: `EfficiencyMetrics`/`AntiLoopGuard`.
- `capt_solo/evidence/guard.py`: `build_guard_decision()`/`reuse_decision()` —
  structured contract a runtime guard consumes to avoid verification loops.
- `capt_solo/evidence/integration.py`: VSI<->Evidence bridge (proof-preserving
  reuse; invalidation marks VSI records affected/unaffected).
- CLI: `capt evidence ...`, `capt mission ...`, `capt selfmod ...`.
- `docs/EVIDENCE_MODEL.md`: operational documentation of the evidence layer.

### Evidence
- `tests/test_evidence_core.py`: 11 passed (evidence core, invalidation, reuse, proof graph).
- `tests/test_evidence_workspace.py`: 17 passed (isolation, promotion, selfmod, checkpoint, metrics).
- `tests/test_evidence_cli.py`: 5 passed (CLI integration).
- `tests/test_evidence_adversarial.py`: 12 passed (representative + negative/adversarial).
- Baseline HEAD `a0124c1` unchanged (clean tree); prior 594-pass verification
  reused per VSI. New evidence-package code is covered by the targeted tests above.

## [0.4.1] — 2026-07-26 (canonical public architecture convergence)

This release repairs the clean-clone/build baseline and aligns the version
identity that had diverged across artifacts.

### Fixed
- **Baseline import defect (DEBT-001):** `capt_solo/ctp/` was gitignored and
  absent from the committed tree, so a fresh clone could not import the public
  API (`ModuleNotFoundError: capt_solo.ctp.journal`). The canonical CTP source
  (project-owned, recovered from the v0.4.1 wheel built from this tree) is now
  committed under `capt_solo/ctp/`. `verify_runtime.py` and the full test suite
  now pass on a clean checkout.
- **Version divergence (DEBT-002):** `pyproject.toml` and `capt_solo/__init__.py`
  declared `0.1.0` while the built wheel, plugin manifest, knowledge-bubble
  manifest, and documentation declared `0.4.x`. Aligned all package-level
  version identifiers to **0.4.1** (the intended public baseline; prior tag was
  `v0.4.0`). Evidence: wheel `capt_solo-0.4.1-py3-none-any.whl`, docs, tag history.

### Added
- Architecture enforcement infrastructure (Phase 3A): ADRs, machine-readable
  registry (`architecture/registry.yaml`), validator (`architecture/validate_registry.py`),
  architectural fitness tests, and architectural debt register. See `docs/adr/`
  and `docs/ARCHITECTURAL_DEBT.md`.

### Evidence
- `verify_runtime.py`: 46/46 checks pass (was 1 pass + skipped on clean clone).
- `pytest`: 374 collected, 374 passed (was 16 collection errors on clean clone).
- `capt_cli.py architecture validate`: registry passes 15 structural checks.

## [0.4.0] — prior tagged release
- Previous tagged baseline (`git tag v0.4.0`). Superseded by 0.4.1.

## Version identity resolution (I-15 — evidence over implementation)
| Source | Before | After | Evidence |
|--------|--------|-------|----------|
| `pyproject.toml` | 0.1.0 | 0.4.1 | metadata bug; wheel built from this tree is 0.4.1 |
| `capt_solo/__init__.py` | 0.1.0 | 0.4.1 | runtime version constant |
| `capt_solo/foundry/bubble.py` `CAPT_SOLO_VERSION` | 0.4.0 | 0.4.1 | knowledge-bubble manifest version |
| `capt_solo/plugin/plugin.json` | 0.4.0 | 0.4.1 | Hermes plugin manifest |
| built wheel | 0.4.1 | 0.4.1 | `dist/capt_solo-0.4.1-py3-none-any.whl` |
| git tag | v0.4.0 | (recommend v0.4.1) | tag creation is a release action, not auto-pushed |

No two equally authoritative release histories were found; 0.4.1 is the
defensible canonical version per I-15.
