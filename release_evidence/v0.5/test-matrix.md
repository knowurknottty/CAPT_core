# CAPT Core v0.5 — Test Matrix and Skip-Reason Reconciliation

## Environment matrix

| Environment | Commit/ref | Python | Platform | Passed | Skipped | Deselected | Failed |
|-------------|-----------|--------|----------|--------|---------|-----------|--------|
| Local installed-lib venv (repo worktree) | 548ab3a | 3.9.6 | macOS | 722 | 44 | 12 | 0 |
| Local fresh venv | 548ab3a | 3.10.20 | macOS | 722 | 44 | 12 | 0 |
| Local fresh venv | 548ab3a | 3.12.13 | macOS | 722 | 44 | 12 | 0 |
| Local simulate-CI (no Hermes on PATH) | 548ab3a | 3.12.13 | macOS | 712 | 54 | 12 | 0 |
| Hosted GitHub Actions (M0-A python 3.10) | 548ab3a | 3.10 | ubuntu-latest | 712 | 54 | 12 | 0 |
| Hosted GitHub Actions (M0-A python 3.12) | 548ab3a | 3.12 | ubuntu-latest | 712 | 54 | 12 | 0 |
| Hosted GitHub Actions (Release-Security 3.10) | 548ab3a | 3.10 | ubuntu-latest | 712 | 54 | 12 | 0 |
| Hosted GitHub Actions (Release-Security 3.12) | 548ab3a | 3.12 | ubuntu-latest | 712 | 54 | 12 | 0 |

## Discrepancy resolution (722/44 vs 712/54)

The totals are **not** a Python-version difference. Both environments use 3.10/3.12. The difference is **platform/external-runtime availability**:

- **44 skips (all environments):** `anti-token-extraction upstream package not installed in this env` — the private anti-token-extraction package is unavailable in hosted CI and in the local test env.
- **10 additional skips (CI Linux and local-with-no-Hermes):** `real Hermes runtime not available on PATH` — these are the `requires_hermes` tests in `tests/capt_runtime/test_hermes_driver.py`. Local macOS has real Hermes on PATH, so these 10 tests PASS locally (722). Hosted CI has no Hermes, so these 10 tests SKIP on CI (712 passed / 54 skipped).

**Reconciliation:**
- Local (Hermes on PATH): 722 passed = (712 base + 10 Hermes tests), 44 skipped
- CI (no Hermes): 712 passed, 54 skipped (44 anti-token + 10 Hermes)
- Total collection identical (778) in both; the 10 Hermes tests either pass (local) or skip (CI).

Machine-reproduced: running local 3.12 with Hermes removed from PATH yields exactly `712 passed, 54 skipped, 12 deselected` — matching hosted CI byte-for-byte.

## Exact skip reasons (from `-rs`)

| Count | Reason |
|-------|--------|
| 44 | anti-token-extraction upstream package not installed in this env |
| 10 | real Hermes runtime not available on PATH (CI only) |

## Deselection reason

12 tests deselected via `pyproject.toml` `addopts = "-m 'not slow'"` — these are the `slow`-marked tests (spawn real external runtime processes). They are deselected by default in all environments unless explicitly run with `-m slow`.

## Prior incorrect claims corrected

- Earlier evidence described skips as "44 skipped (anti-token-extraction optional dep)" without the 10 Hermes-dependent skips on CI. This report separates them.
- Earlier report conflated local 722 and CI 712 into one "722 passed" claim. The PR body and this report now report both distinctly.
- The Python-3.14-only memory-engine migration error (`test_global_degradation_language`) is an environment artifact of Python 3.14 on this local machine and is **not** present in the released Python versions (3.10/3.12) or the CI runs.

## Note on "slow" vs Hermes skips

Not all skips are "slow" markers — only the 12 deselects correspond to slow markers. The 44 anti-token and 10 Hermes-unavailable skips are runtime/optional-dependency skips. This is stated precisely.
