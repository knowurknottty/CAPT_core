# FINAL_RELEASE_AUDIT — CAPT Core v0.5 Release Board Decision

Candidate SHA: `7b9bcf422c69d3afbbe600d64239c6dd8c3cea71`
Date: 2026-07-30. Process: implementation → HY3 recursion (P1/P2) → independent
evidence audit (P3) → independent documentation audit (P4) → this decision.

## Single question
**Is CAPT Core v0.5 ready to be frozen and released, and if not, what exact
evidence-backed blockers remain?**

## Answer
**NOT READY TO FREEZE.** Two evidence-backed blockers remain. Both are
documentation/metadata defects (not code defects), and both are fixable in
minutes. No code-level blocker exists.

## Blockers (evidence-backed)

### BLOCKER 1 — Release validator fails (F1 / Pass 3)
- Evidence: `capt_cli release validate` → `public_api.package_inventory: fail`.
  Declared stable packages (18) omit `capt_solo.components`; source tree has 19.
- Cause: OD-4 recovered the ATE component (`capt_solo.components`) but did not
  update `docs/release/PUBLIC_API_MANIFEST_V0.5.json` declared package list.
- doc 07 machine-enforced failure: "an advertised package is missing" → release
  MUST fail. This is a hard gate, not advisory.
- Prior reports (BASELINE_REVALIDATION, EXACT_SHA_RELEASE_VALIDATION) incorrectly
  stated the validator passes — independent re-run (Pass 3) contradicts them.
- Fix: add `"capt_solo.components"` to the manifest declared stable list
  (one-line metadata edit). Then `release validate` should pass.
- Owner action required: approve the manifest edit (metadata correction, not
  code). Alternatively authorize HY3 to apply it.

### BLOCKER 2 — Missing public security/verification reports (F5 / Pass 4)
- Evidence: README links to `docs/security/RELEASE_SECURITY_REPORT_V0.5.md` and
  `docs/release/RELEASE_VERIFICATION_V0.5.md` — both ABSENT. GitHub visitors hit
  404; security reviewers cannot assess the project.
- Cause: doc 07 requires these at freeze; they were never generated (B8 process
  blocker from Pass 1/2).
- Fix: generate both docs from the evidence already collected (gitleaks no
  leaks, verify_runtime 52/1/0, ATE invariants, 715 tests, artifact hashes in
  release_evidence/*.json). Owner-gated process step.
- Owner action required: authorize generation, or temporarily soften README
  links to existing SECURITY_BOUNDARIES.md / RELEASE_GOVERNANCE.md.

## Non-blocking findings (recommend, don't block)
- F2 (Pass 3): public API more complex than README implies — add construction
  snippets. Clarity only.
- F6 (Pass 4): state deferred v0.5.1 scope (Spaces/adapters) in public docs.
- F8 (Pass 4): clarify Hermes is optional in architecture diagram caption.

## What passed (independent verification)
- 18/19 capability chains terminate in code+tests+wheel (Pass 3).
- 715 tests pass (rerun this session, not inherited).
- Wheel + sdist install clean; no-network import; zero Hermes imports.
- Version strings consistent (0.5.0); terminology consistent across all docs.
- ATE recovered, optional/degradable, provenance-pinned.
- LICENSE in wheel; gitleaks clean; doctor injection tests pass.

## Residual accepted risk
- ATE depends on optional external `anti-token-extraction` package (not bundled,
  degrades gracefully). By design.
- bandit/semgrep/pip-audit not run locally at SHA — will run in release-security
  CI on push (owner authorization required for push).

## Decision
**STATUS: NOT READY — 2 BLOCKERS (B1 manifest, B2 missing reports).**
Both are owner-gated documentation/metadata steps. No code change required.
Once B1 + B2 are resolved and `capt release validate` passes clean, the
candidate is ready for owner freeze authorization (tag/publish/merge to main —
all separately authorized per standing rules).

## Files changed by this audit
NONE. Passes 3-4 were audit-only. The blocker fixes require owner approval or a
subsequent authorized implementation step.
