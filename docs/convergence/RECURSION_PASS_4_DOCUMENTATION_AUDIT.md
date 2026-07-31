# RECURSION_PASS_4_DOCUMENTATION_AUDIT — External Credibility Review

Auditor: Independent (Pass 4). Date: 2026-07-30. Candidate `7b9bcf4`.
Personas: PyPI user, GitHub visitor, OSS maintainer, security reviewer, new
architect. No repo modified. Recommendations only.

## Can a reader understand, without prior knowledge?

| Question | Answerable from repo? | Evidence |
|---|---|---|
| What is CAPT? | YES | README L1-13, whitepaper |
| What isn't it? | YES | README "What CAPT Does Not Do" |
| What is implemented? | YES | six pillars + tests |
| What is experimental? | YES | PULSE (README Local-First), research heritage |
| What is deferred? | PARTIAL | OD-1/OD-2 ratified but NOT stated in public docs — a reader can't tell Spaces/adapters are v0.5.1 from README alone |
| What belongs in v0.5.1? | NO | no public doc states the v0.5.1 scope |
| How to install? | YES | README Five-Minute Flow + Installed CLI |
| How to verify? | YES | README Verification Commands + verify_runtime.py |
| How to trust? | PARTIAL | security report doc referenced but MISSING (see F5) |

## Broken navigation (GitHub visitor hits 404)
- README "Security and Release Status" links `docs/security/RELEASE_SECURITY_REPORT_V0.5.md` → **file does not exist**.
- README "Verification Commands" references `docs/release/RELEASE_VERIFICATION_V0.5.md` → **file does not exist**.
- These are the B8 process-blocker docs (Pass 1/2). Until generated, the README
  promises docs that 404. A security reviewer immediately loses trust.

## Overstatement / marketing language
- "Secure, Auditable, Model-Agnostic" (whitepaper title) — TRUE (gitleaks, ATE,
  doctor, injection tests, zero Hermes). Not marketing without backing.
- "runs underneath models and protocols rather than requiring one provider" —
  TRUE (architecture-level neutrality evidenced).
- No "enterprise-grade", "production-ready", or unbacked superlatives found.

## Internal terminology consistency
- Core / Solo / Space / adapter / Hermes: consistent. Spaces never claimed
  present. Adapters framed as architecture layer + future (whitepaper L498
  "adapter seam", PUBLIC_ARCHITECTURE L104 "future adapter"). ✅
- "model-agnostic" used consistently (architecture-level, true). ✅

## Stale version references
- README: v0.5.0 throughout. ✅
- Whitepaper L451: corrected to v0.5.0 (OD-4). ✅
- PUBLIC_ARCHITECTURE: v0.5. ✅
- No v0.4.1 language in public docs (verified). ✅

## Duplicate concepts
- `antitoken` (memory compression) vs `anti_token_extraction` (components) —
  distinct, now documented (Pass 1 F1). ✅ Low confusion risk.

## Findings

### F5 — README links to two non-existent release docs [HIGH/MEDIUM]
- Evidence: `docs/security/RELEASE_SECURITY_REPORT_V0.5.md` and
  `docs/release/RELEASE_VERIFICATION_V0.5.md` referenced in README but absent.
- Impact: broken navigation; security reviewer distrust; doc 07 requires these
  files before freeze.
- Disposition: generate both (owner-gated B8) OR temporarily soften README links
  to "will be generated at freeze." Recommend generating before freeze.

### F6 — v0.5.1 scope not stated publicly [MEDIUM]
- Evidence: OD-1/OD-2 ratified (Spaces/adapters → v0.5.1) but no public doc
  tells a reader what is deferred. A reader may assume the six pillars ARE the
  whole product and be surprised later.
- Disposition: add a one-line "Deferred to v0.5.1" note to README or
  PUBLIC_ARCHITECTURE. Low effort, improves honesty.

### F7 — manifest omits components [HIGH, same as F1]
- Evidence: PUBLIC_API_MANIFEST_V0.5.json declared stable lacks
  capt_solo.components (recovered in OD-4). Release validator FAILS.
- Disposition: add capt_solo.components to manifest. (Cross-ref Pass 3 F1.)

### F8 — "Adapters: ... Hermes ..." diagram line [LOW]
- Evidence: PUBLIC_ARCHITECTURE L15 lists Hermes among adapter surfaces. True as
  an architecture layer, but a skimming reader could infer Hermes is required.
  The same doc L104 says "future adapter may translate" — mitigating.
- Disposition: add "(Hermes is one optional integration, not required)" to the
  diagram caption. Clarity only.

### F9 — docs not in wheel [LOW, accepted]
- Standard packaging. GitHub is the doc source. Accepted.

## Reader-persona verdict
- New user: can install + verify from README. ✅ (except 404 links)
- Experienced Python dev: understands architecture from PUBLIC_ARCHITECTURE. ✅
- Enterprise evaluator: lacks explicit deferred-scope + security report (F5/F6).
- Security auditor: blocked by missing security report (F5). Distrust risk.
- Contributor: needs DEFERRED scope stated (F6) to know what NOT to build yet.

## Recommendation
Fix F5 (generate/soften links) + F7 (manifest) before freeze. F6/F8 are
low-effort honesty improvements. No implementation or scope change.
