# Changelog

All notable changes to CAPT Solo are documented here. This project adheres to
semantic versioning. The canonical public baseline is **v0.4.1**.

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
