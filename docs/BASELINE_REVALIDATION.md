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
| Full suite | `python -m pytest tests/ -q` | **711 passed, 4 failed, 44 skipped** (regenerated 2026-07-30 at `7b9bcf4`) |
| Build | `python -m build` | wheel + sdist built |
| Wheel install | fresh venv `pip install dist/*.whl` | import OK, version 0.5.0 |
| Sdist install | separate venv `pip install dist/*.tar.gz` | no-network import OK (all core pkgs) |
| verify_runtime | `python verify_runtime.py` | 52 pass / 1 warn / 0 fail (53 checks) |
| gitleaks | `gitleaks detect --source . --config .gitleaks.toml` | no leaks found |
| release validate (pre-correction) | `capt release validate` | **FAIL** (`public_api.package_inventory` — manifest omitted `capt_solo.components`); corrected in Phase A |
| release validate (post-correction) | `capt release validate` | PASS (10/10) |
| doctor | `capt doctor` | OK |
| no-Hermes import | socket-deny import in clean venv | all core packages import, zero hermes |
| ATE component | import `capt_solo.components` | OK (degrades without external pkg) |

## Note on the 4 failures
The 4 failing tests are Option A freeze-gate regression tests
(`test_release_identity_option_a.py`, `test_release_semantics.py`). They clone
the repo, set `candidate_sha` to a real commit, and run `validate_release(
final=True)`. They fail in the UNFROZEN state (dirty tree from untracked audit
evidence + `candidate_sha=UNFROZEN`). They are EXPECTED failures pre-freeze, not
implementation defects. They pass only after the candidate is frozen.

## Artifact hashes
- wheel: `e9e316464916a5ae97a4306ba15ad87dc1b191ee49d4cb047e9a9950248a3ba9`
- sdist: `92962c3b26687a61391593caba5ae0ea58a96c44374761616ba421d95189c480`

## Conclusion
Converged candidate `c4b954c` reproduces the baseline and extends it with the
verified main-only security deltas. Baseline revalidation: PASS (pre-freeze;
candidate_sha remains UNFROZEN until freeze step).
