# RECURSION_PASS_2_RELEASE_TRUTH — Contract & Release Falsification

Generated: 2026-07-30 (HY3 Recursive Pass 2). Attempted to DISPROVE that the
candidate is truthful and releasable. Re-derived from the resulting repo
(`c4b954c`), not prior reports. Adversarial questions applied.

## Review surface
README, whitepaper, PUBLIC_ARCHITECTURE.md, API manifest, CLI help, examples,
trust/security docs, version strings, claim ledger, exact-SHA evidence,
reproducibility, release process.

## Adversarial questions

### Q: What claim is technically true but misleading?
- "Secure, Auditable, Model-Agnostic Cognitive Infrastructure" (whitepaper
  title). TRUE: gitleaks clean, ATE provenance gates, doctor injection tests,
  command-injection hardening, zero Hermes imports, no network on import. Not
  misleading — evidence exists. ✅
- "model-agnostic" — TRUE at architecture level (evidenced). v0.5.0 does NOT
  claim an operational adapter framework (OD-2 ratified; A16 seam wording
  applied). ✅

### Q: What works only from a source checkout?
- Docs (WHITEPAPER.md, PUBLIC_ARCHITECTURE.md) are NOT in the wheel — only in
  sdist + GitHub. Standard Python packaging; README points to GitHub for docs.
  No claim asserts docs ship in wheel. ✅ (LOW/accepted: wheel users read docs
  on GitHub, which is normal.)

### Q: What is undocumented?
- antitoken vs anti_token_extraction distinction — now documented (Pass 1 F1).
- ATE optional external dependency — documented in ANTI_TOKEN_EXTRACTION.md
  (provenance pin, degrades without external pkg). ✅

### Q: What limitation is buried?
- ATE requires optional external `anti-token-extraction` package (not bundled);
  degrades to no-op without it. Stated in ANTI_TOKEN_EXTRACTION.md. ✅
- Spaces / runtime adapters explicitly deferred to v0.5.1 (OD-1/OD-2). No
  public doc claims them present. ✅

### Q: What evidence cannot be reproduced?
- bandit/semgrep/pip-audit not yet run at SHA (Pass 1 F3). Reproducible via
  release-security.yml on push. gitleaks + verify_runtime ARE reproduced today.
  → owner-gated, not a falsification.

### Q: What file still implies the wrong release?
- FULL_ARCHITECTURE_IMPLEMENTATION_MATRIX.md falsely claimed `ctp/journal.py`
  is gitignored/missing. VERIFIED FALSE — file is tracked + present. Corrected
  with a superseded header this pass. (See F7.)

### Q: What future seam is presented as a current feature?
- A16 "adapter seam" (fixed from "adapters"). Architecture doc L104 "a future
  adapter may translate" is explicitly future. ✅ No overstatement.

### Q: What security claim lacks implementation evidence?
- None. "secure": gitleaks + ATE + doctor + injection tests. "auditable": CTP
  append-only + evidence provenance. All evidenced. ✅

### Q: What would a skeptical senior engineer challenge?
- "715 tests" — reproduced today (post-convergence), not inherited. ✅
- "no Hermes dependency" — proven via socket-deny import + zero `import hermes`.
  ✅
- LICENSE present in wheel — verified (dist-info/licenses/LICENSE). ✅

## Findings

### F7 — FALSE claim CTP missing from tree [MEDIUM → RESOLVED]
- FULL_ARCHITECTURE_IMPLEMENTATION_MATRIX.md asserted ctp/journal.py gitignored
  / missing. VERIFIED: tracked + present (8048 bytes). Misleading to reviewers.
- Disposition: RESOLVED this pass (superseded header + correction note).

### F8 — docs not in wheel [LOW → ACCEPTED]
- Standard packaging; no claim asserts otherwise. Accepted.

### F9 — release-security scan at SHA pending [MEDIUM → OWNER_GATED]
- Same as Pass 1 F3. bandit/semgrep/pip-audit not run locally; CI runs on push.

### F10 — security report doc pending [MEDIUM → OWNER_GATED]
- Same as Pass 1 F4. RELEASE_SECURITY_REPORT_V0.5.md not generated.

## Verdict
No BLOCKER, no HIGH. One MEDIUM (F7) resolved. Two MEDIUM (F9/F10) are the same
owner-gated pre-freeze process steps as Pass 1. Public claims are truthful:
every material claim maps to implementation + tests + runtime/package evidence.
No future seam presented as current feature. The candidate is releasable
subject to owner freeze authorization + the two process steps (security scan at
SHA, security report doc).
