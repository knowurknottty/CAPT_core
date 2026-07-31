# PUBLIC_CREDIBILITY_REVIEW — Pass 4

Candidate `7b9bcf4`. External credibility assessment (PyPI user / GitHub visitor
/ security reviewer lens). Recommendations only; no changes made.

## Strengths (credibility builders)
1. Honest pre-release framing: README states "not published, tagged, or
   approved" and "no tag/publication/merge authorized by passing local
   verification." Self-binding language builds trust.
2. "What CAPT Does Not Do" explicitly bounds claims (no legal/scientific/
   security correctness by branding). Rare and credible.
3. Local-first is evidenced (socket-deny import test, zero Hermes imports) — not
   just asserted.
4. Verification-first example runs with no network and shows invalidation —
   demonstrable, not decorative.
5. Version strings consistent everywhere (0.5.0).
6. ATE is honestly "optional, degradable" with provenance pin — no hidden dep.

## Credibility hazards
1. **Missing security report (F5).** README links to
   `docs/security/RELEASE_SECURITY_REPORT_V0.5.md` which 404s. A security
   reviewer's first click fails. For a project whose tagline is "secure,
   auditable," this is the single biggest credibility gap. MUST fix before any
   public push.
2. **Missing verification report (F5).** Same for RELEASE_VERIFICATION_V0.5.md.
3. **Validator-PASS claim was false (Pass 3 F1).** If an external reviewer runs
   `capt release validate` they see FAIL — directly contradicting the repo's own
   EXACT_SHA_RELEASE_VALIDATION.md. That contradiction destroys trust faster
   than the bug itself. Fix F1 + correct the doc.
4. **Deferred scope undisclosed (F6).** A reader cannot tell Spaces/adapters are
   v0.5.1. If they later discover it, it reads as a bait-and-switch. State it.
5. **"Adapters: Hermes" diagram (F8).** Minor; could imply Hermes required.

## Would each persona reach the same understanding?
- PyPI user: installs, runs `capt doctor`, sees local-first. ✅ (if docs links
  fixed)
- GitHub visitor: reads README, clicks security link → 404. ❌ (F5)
- OSS maintainer: reviews architecture docs → consistent, honest. ✅
- Security reviewer: no security report → cannot assess. ❌ (F5)
- New architect: understands six pillars; unclear what's deferred. ⚠️ (F6)

## Recommended wording improvements (only)
1. README Security section: change the two links to point to existing
   SECURITY_BOUNDARIES.md + RELEASE_GOVERNANCE.md until the v0.5 reports are
   generated; OR generate the reports before freeze.
2. README: add one line — "Spaces and the operational provider-neutral runtime
   adapter contract are planned for v0.5.1; v0.5.0 ships the verification
   substrate described here."
3. PUBLIC_ARCHITECTURE diagram caption: "(Hermes is one optional integration,
   not a required dependency)."
4. Correct EXACT_SHA_RELEASE_VALIDATION.md: the validator does NOT pass until
   F1 is fixed; state the actual `public_api.package_inventory` failure.
5. API manifest: add `capt_solo.components` to declared stable packages.

## Verdict
Credibility is HIGH on substance (honest bounds, evidenced local-first,
demonstrable verification) but UNDERMINED by two missing docs (F5) and one false
validator claim (F1). Fix F1 + F5 before any public release. F6/F8 are quick
honesty wins.
