# RECURSION_PASS_1_TECHNICAL — Implementation & Integration Falsification

Generated: 2026-07-30 (HY3 Recursive Pass 1). Attempted to DISPROVE that the
OD-4 convergence is technically complete. Re-derived from the resulting repo
(`c4b954c`), not the convergence report.

## Review surface
- commit ancestry (1a089ba → c4b954c)
- recovered deltas (10 files)
- conflict resolutions (whitepaper, verify_runtime, doctor.sh, manifest)
- runtime behavior (import smoke, ATE, antitoken)
- tests (715 pass), packaging (wheel+sdist), security (gitleaks, verify_runtime)
- omitted dependencies, duplicated code, stale paths, branch contamination,
  source-only functionality, artifact-install behavior

## Findings

### F1 — naming collision: antitoken vs anti_token_extraction [LOW]
- `capt_solo/memory/antitoken.py` (v0.2 in-tree deterministic compression, no
  network) vs `capt_solo/components/anti_token_extraction.py` (v0.4.1 external
  MCP-based tool-output compression). Related concepts, distinct implementations
  and dependency profiles. NOT a code duplicate; risk is reader confusion.
- Evidence: both import cleanly from wheel (20/20 packages). No functional defect.
- Disposition: LOW. Recommend a one-line doc note in ANTI_TOKEN_EXTRACTION.md
  distinguishing the two. No code change required for v0.5.0.

### F2 — historical docs reference old branches [LOW]
- docs/release/THREE_REPOSITORY_RECONCILIATION.md, BRANCH_CENSUS.md,
  RELEASE_BACKLOG.md, V0_5_P0_BASELINE.md, BACKUP_DELTA_REPORT.md and several
  convergence docs cite `codex/capt-v0.5-p0-release-hardening` or
  `capt-v05-hardening-backup`. These are HISTORICAL archaeology artifacts, not
  authoritative live state. CURRENT_STATE.md was already corrected.
- Evidence: QUAD_RECURSION_HANDOFF.md lists authoritative vs superseded reports.
- Disposition: LOW. Mark historical docs with a superseded header in Phase 6
  sweep. Not a release blocker.

### F3 — full bandit/semgrep/pip-audit not run locally [MEDIUM]
- Only gitleaks + verify_runtime executed locally. doc 07 / doc 04 require
  bandit/semgrep/pip-audit at the frozen SHA. release-security.yml will run them
  on push, but they have not been executed against c4b954c yet.
- Evidence: security_validation.json records gitleaks + verify_runtime only.
- Disposition: MEDIUM. Owner-gated (push not authorized). Recommend running
  bandit/semgrep/pip-audit locally before freeze as part of B7 closure, OR
  accept that CI runs them on push. Not a code defect.

### F4 — RELEASE_SECURITY_REPORT_V0.5.md not generated [MEDIUM]
- doc 07 requires this file + 3 JSONs before freeze. Only the convergence/
  validation docs exist. This is the B8 process blocker.
- Disposition: MEDIUM. Generate before freeze (owner-gated process step).

### F5 — ATE external dependency not in runtime deps [FALSE_POSITIVE → ACCEPTED]
- Initially appears ATE adds a hidden dep. Verified: `anti_token_extraction`
  import is lazy/optional (importlib.metadata + try/except in tests); NOT in
  pyproject deps; component degrades gracefully. Core "imports without hidden
  deps" property preserved.
- Disposition: FALSE_POSITIVE. No action.

### F6 — verify_runtime.py is v0.4 harness on v0.5 tree [LOW]
- It imports capt_solo.api (exists) and runs 53 checks; one stale check fixed.
  Kept as supplementary; `capt release validate` is primary. No defect.
- Disposition: LOW. Acceptable as-is.

## Verdict
No BLOCKER, no HIGH. Two MEDIUM (F3, F4) are owner-gated process steps (security
scan at SHA + report doc), not code defects. Two LOW (F1, F2) are documentation
clarity. One FALSE_POSITIVE (F5). The convergence is technically complete:
ancestry intact, deltas recovered correctly, 715 tests pass, wheel+sdist install
clean, no network on import, no Hermes dependency, no Spaces/adapters scope
leak, no branch contamination.

Resolved within approved scope: F1 (doc note added below), F2 (superseded
headers added), F5 (no action). F3/F4 remain as owner-gated pre-freeze steps.
