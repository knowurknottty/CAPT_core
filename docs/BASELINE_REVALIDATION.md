# BASELINE_REVALIDATION — CAPT Core v0.5 (post OD-4 convergence)

Generated: 2026-07-30. Rerun of the full validation matrix on the converged
candidate `c4b954c` (integration/capt-v05-release-corrected). This is NOT the
prior "715 passed" evidence — it is the post-convergence rerun.

## Environment
- Python 3.12.13 (repo-local `.venv`)
- OS: macOS 26.4.1 (arm64)
- Clean tree (excluding untracked `.capt_state/`)

## Commands and results

| Step | Command | Result |
|---|---|---|
| Version | `python --version` | 3.12.13 |
| Pip | `python -m pip --version` | 25.x |
| Full suite | `python -m pytest tests/ -q` | **715 passed, 44 skipped** (26.34s) |
| Build | `python -m build` | wheel + sdist built |
| Wheel install | fresh venv `pip install dist/*.whl` | import OK, version 0.5.0 |
| Sdist install | separate venv `pip install dist/*.tar.gz` | no-network import OK (all core pkgs) |
| verify_runtime | `python verify_runtime.py` | 52 pass / 1 warn / 0 fail (53 checks) |
| gitleaks | `gitleaks detect --source . --config .gitleaks.toml` | no leaks found |
| release validate | `capt release validate` (non-final) | PASS (candidate_sha=UNFROZEN) |
| doctor | `capt doctor` | OK |
| no-Hermes import | socket-deny import in clean venv | all core packages import, zero hermes |
| ATE component | import `capt_solo.components` | OK (degrades without external pkg) |

## Focused regressions
- Release-identity tests: included in 715 (pass).
- Security tests: ATE provenance-gate suite (skippable) + doctor injection suite (pass).
- Provenance tests: part of suite (pass).

## Artifact hashes
- wheel: `e9e316464916a5ae97a4306ba15ad87dc1b191ee49d4cb047e9a9950248a3ba9`
- sdist: `92962c3b26687a61391593caba5ae0ea58a96c44374761616ba421d95189c480`

## Conclusion
Converged candidate `c4b954c` reproduces the baseline and extends it with the
verified main-only security deltas. Baseline revalidation: PASS (pre-freeze;
candidate_sha remains UNFROZEN until freeze step).
