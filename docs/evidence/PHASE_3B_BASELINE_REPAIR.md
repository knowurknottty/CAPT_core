# Phase 3B — Baseline Repository and Packaging Repair

**Branch:** integration/full-public-architecture
**Date:** 2026-07-26
**Issue:** #5
**Preceded by:** Phase 3A (commit 1d1744d)

## Objective
A fresh clone or clean checkout must contain all required runtime source, not
depend on an untracked local wheel, install with documented commands, build
successfully, collect tests, execute baseline verification, and expose a single
coherent version identity.

## 3B.1 — CTP Source Restoration (DEBT-001)

### Investigation
- `git ls-files capt_solo/ctp/` returned **empty** on the committed tree.
- `.gitignore` contained the line `ctp/` (line 13), excluding the entire
  `capt_solo/ctp/` runtime package from version control.
- The installed/bundled wheel `dist/capt_solo-0.4.1-py3-none-any.whl` (built from
  this exact tree) **contains** `capt_solo/ctp/__init__.py` and
  `capt_solo/ctp/journal.py`.
- `capt_solo/api.py` imports `from capt_solo.ctp.journal import CTPRuntime, Receipt`,
  so the missing package broke the entire public API on a clean clone.

### Resolution
- The CTP source is **project-owned** (it is capt-solo's own runtime package, not
  an external dependency). The wheel built from this tree is lawful project
  evidence of the source.
- Restored `capt_solo/ctp/__init__.py` and `capt_solo/ctp/journal.py` from the
  verified wheel source into the tree.
- Removed the `ctp/` exclusion from `.gitignore`.
- **Provenance:** source recovered from `dist/capt_solo-0.4.1-py3-none-any.whl`
  (built from this repository tree). No decompilation; the wheel is the project's
  own build artifact. Public behavior preserved (CTPRuntime/Receipt API unchanged).

### Verification
- `from capt_solo.ctp.journal import CTPRuntime, Receipt` → imports OK.
- `verify_runtime.py`: **46/46 checks pass** (was 1 pass + skipped on clean clone).
- `pytest`: **374 collected, 374 passed** (was 16 collection errors on clean clone).
- Clean-venv install: CTPRuntime instantiates, begin/validate/commit/integrity_check
  all functional.

## 3B.2 — Version Divergence Resolution (DEBT-002)

### Evidence
| Source | Before | After |
|--------|--------|-------|
| `pyproject.toml` | 0.1.0 | 0.4.1 |
| `capt_solo/__init__.py` | 0.1.0 | 0.4.1 |
| `capt_solo/foundry/bubble.py` `CAPT_SOLO_VERSION` | 0.4.0 | 0.4.1 |
| `capt_solo/plugin/plugin.json` | 0.4.0 | 0.4.1 |
| built wheel | 0.4.1 | 0.4.1 (unchanged) |
| git tag | v0.4.0 | (recommend v0.4.1) |

### Decision (I-15 — evidence over implementation)
The intended public baseline is **v0.4.1**. Evidence is consistent and singular:
- The wheel built from this tree is `0.4.1`.
- Documentation and the plugin/bubble manifests declared `0.4.x`.
- The prior tag is `v0.4.0`, making `0.4.1` the natural next patch.
- `0.1.0` in `pyproject.toml`/`__init__.py` is a stale metadata bug (never bumped
  when the wheel was built at 0.4.1).

No two equally authoritative release histories were found, so no owner escalation
under `[C]` is required. The `0.1.0` defaults inside `skill_foundry.py` are
**skill-artifact** versions (a separate namespace) and were intentionally left
unchanged to avoid altering skill-creation behavior.

A `v0.4.1` git tag is **recommended** but not created/pushed here (tag creation is
a release action outside this autonomous phase; per repository workflow, tags are
not auto-pushed).

## 3B.3 — Clean Build Validation

Performed in an isolated temp environment (no developer-local paths, no cached
editable installs, no untracked artifacts, no stale wheels in the build dir):

```
$ python3 -m build --outdir /tmp/capt_cleanbuild
Successfully built capt_solo-0.4.1.tar.gz and capt_solo-0.4.1-py3-none-any.whl

$ python3 -m zipfile inspect: wheel contains
    capt_solo/ctp/__init__.py
    capt_solo/ctp/journal.py
    (56 files total)

$ python3 -m venv /tmp/capt_venv
$ /tmp/capt_venv/bin/pip install capt_solo-0.4.1-py3-none-any.whl
$ cd /tmp && /tmp/capt_venv/bin/python -c "import capt_solo; from capt_solo.ctp.journal import CTPRuntime; print(capt_solo.__version__)"
clean import OK, version 0.4.1

$ CTPRuntime begin/validate/commit/integrity_check in clean venv → OK
```

### pyproject.toml restructuring
The previous `pyproject.toml` mixed PEP 621 `[project]` with legacy `[options]`
`packages`, which broke setuptools auto-discovery during `build`. Restructured to
PEP 621 `[project]` + explicit `[tool.setuptools] packages` list (including
`capt_solo.ctp`) + `[project.entry-points.hermes_plugins]`. Build now succeeds.

## Result
- Fresh clone now contains all runtime source (CTP included).
- No dependency on an untracked local wheel.
- `python3 -m build` produces a valid wheel + sdist.
- Wheel installs into a clean venv and imports/executes correctly.
- Single coherent version identity: **0.4.1** across metadata, runtime, plugin,
  bubble manifest, and wheel.
- `verify_runtime.py` and `pytest` pass on the tree.

## Tests added
- `tests/test_phase3b_baseline.py`: version-identity consistency, CTP source
  presence + importability, and gitignore exclusion check.

## Remaining
- Tag `v0.4.1` (owner/release action, not auto-pushed).
- Subsequent phases (3C+) build on this repaired baseline.
