# QUAD_RECURSION_HANDOFF — CAPT Core v0.5

Generated: 2026-07-30. Handoff for the four recursive review passes + final audit.

## Exact candidate SHA
`c4b954cc2d3168c3bc5345fab0c0e5d0eaa9ebea`
Branch: `integration/capt-v05-release-corrected`
Base lineage: 716ecc9 (verified) → 1a089ba (pre-OD4) → c4b954c (converged)

## Repository state
- Path: /Users/knowurknot/capt-solo
- Clean tree (excluding untracked .capt_state/)
- Python 3.12.13 venv
- Safety tag: `od4-rollback-1a089ba` (pre-convergence anchor)

## Commands run (this session)
- `pytest tests/ -q` → 715 passed, 44 skipped
- `python -m build` → wheel + sdist
- wheel clean-install (fresh venv) → import OK
- sdist clean-install (separate venv, socket-deny) → no-network import OK
- `python verify_runtime.py` → 52 pass / 1 warn / 0 fail
- `gitleaks detect` → no leaks
- `capt release validate` (non-final) → PASS (UNFROZEN)
- `capt doctor` → OK

## Test totals
715 passed, 44 skipped (2600+ collected; 44 are environment/skip conditions).

## Package artifacts
- wheel: `dist/capt_solo-0.5.0-py3-none-any.whl`
  sha256 `e9e316464916a5ae97a4306ba15ad87dc1b191ee49d4cb047e9a9950248a3ba9`
- sdist: `dist/capt_solo-0.5.0.tar.gz`
  sha256 `92962c3b26687a61391593caba5ae0ea58a96c44374761616ba421d95189c480`
- LICENSE in wheel: yes (dist-info/licenses/LICENSE)
- ATE component in wheel: yes (optional, degradable)

## Evidence locations
- docs/convergence/OD4_PRECONVERGENCE_STATE.md
- docs/convergence/OD4_DELTA_LEDGER.md
- docs/BASELINE_REVALIDATION.md
- docs/EXACT_SHA_RELEASE_VALIDATION.md
- release_evidence/exact_sha_validation.json
- release_evidence/package_install_validation.json
- release_evidence/security_validation.json
- docs/FINAL_RELEASE_BLOCKERS.md
- docs/convergence/SPACE_TRACEABILITY_MATRIX.md
- docs/convergence/RUNTIME_CAPABILITY_MATRIX.md
- docs/convergence/PUBLIC_ARCHITECTURE_TRACEABILITY.md
- docs/convergence/DEFERRED_SCOPE_VALIDATION.md
- docs/convergence/RELEASE_INTEGRITY_ASSESSMENT.md (corrected per owner)
- docs/convergence/OWNER_DECISION_REGISTER.md (OD-1/OD-2 ratified)

## Changed-file summary (OD-4 convergence)
Recovered (additive): ATE component + mcp.json + tests, .gitleaks.toml,
release-security.yml (synthesized), verify_runtime.py (corrected), whitepaper
(corrected), DESIGN.md, ARCHITECTURE_REVIEW_ATE_ADAPTER.md, ANTI_TOKEN_EXTRACTION.md.
Corrected: PUBLIC_API_MANIFEST_V0.5.json (UNFROZEN), CURRENT_STATE.md (branch
name), test_distribution_contract.py (+components), verify_runtime.py (47→>=1),
whitepaper L451/L498.
Reverted: doctor.sh (kept integration version, rejected main's stale version).

## Unresolved questions
- B7: full bandit/semgrep/pip-audit CI scan not yet run locally (only gitleaks +
  verify_runtime). release-security.yml will run them on push.
- B8: RELEASE_SECURITY_REPORT_V0.5.md not yet generated (process step).

## Accepted risks
- ATE component depends on optional external `anti-token-extraction` package
  (NOT in runtime deps); degrades gracefully. This is by design (independently
  degradable capability) and preserves "core imports without hidden deps."
- verify_runtime.py is a v0.4 harness kept as supplementary; `capt release
  validate` is the primary gate.

## Superseded reports
- BATCH1_CHERRYPICK_IMPACT.md (obsolete — backup has zero unique commits;
  recovery sourced from main, not backup).
- Any doc stating "integration branch is codex/capt-v0.5-p0-release-hardening"
  (CURRENT_STATE.md corrected).

## Authoritative reports
- CROSS_REPOSITORY_SOURCE_OF_TRUTH.md
- TREASURE_CHEST_REQUIREMENTS.md
- V0_5_SCOPE_RECONCILIATION.md
- OWNER_DECISION_REGISTER.md (OD-1/OD-2 ratified)
- OD4_PRECONVERGENCE_STATE.md + OD4_DELTA_LEDGER.md
- BASELINE_REVALIDATION.md + EXACT_SHA_RELEASE_VALIDATION.md

## Expected review order
1. HY3 Recursive Pass 1 — technical/integration falsification
2. HY3 Recursive Pass 2 — contract/release-truth falsification
3. External Recursive Pass 3 — evidence-chain audit (owner)
4. External Recursive Pass 4 — hostile outsider audit (owner)
5. Final Complete Audit

## Instruction
No prior conclusion is immune from falsification. Each pass must re-derive
findings from the resulting repository, not from the convergence report.
Spaces and runtime adapters are OUT OF SCOPE for v0.5.0 (OD-1/OD-2 ratified);
do not treat their absence as a blocker.
