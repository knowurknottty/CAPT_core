# FINAL_V0_5_GAP_REPORT — CAPT Core v0.5

Generated: 2026-07-30
Scope: ONLY genuine blocking, strongly-recommended, and documentation-required
gaps. Research/external/post-v0.5 excluded (see TREASURE_CHEST_REQUIREMENT_MATRIX).

## Release necessity test results

### BLOCKING (release correctness, security, installability, public API integrity, or exact-SHA evidence depends on it)

| Gap | Why blocking | Evidence | Disposition |
|-----|--------------|----------|-------------|
| B1. Exact-SHA security closure incomplete | Treasure Chest doc 07 requires RELEASE_SECURITY_REPORT + findings/coverage/manifest JSON; Codex scan failed (doc 02/11). No final scan exists. | doc 02 "Not confirmed"; doc 11 postmortem | BLOCKING per Treasure Chest. Owner may accept exception (doc 03: no Critical/High open without documented owner exception). |
| B2. Required final release-evidence files absent | doc 07 lists RELEASE_VERIFICATION_V0.5.md, ARTIFACT_MANIFEST, PACKAGE_CONTENTS, CONFORMANCE_RESULTS — all ABSENT. | file check (this review) | BLOCKING per doc 07 machine-fail conditions. |
| B3. Space architecture (doc 15-D) | Treasure Chest finish-line playbook lists it as v0.5 workstream. If v0.5 contract includes it, it is blocking. | doc 15 Workstream D | BLOCKING ONLY IF owner confirms Spaces are in v0.5 scope (OWNER_DECISION #1). If narrowed to six-pillar, downgrade to POST_V0_5. |
| B4. Provider-neutral runtime adapter (doc 15-E) | Same as B3 — required by doc 15-E. | doc 15 Workstream E | BLOCKING ONLY IF owner confirms (OWNER_DECISION #1). |
| B5. Trust Center / Threat Model / SBOM (doc 15-F) | Required by doc 15-F + doc 08. | doc 15/08 | BLOCKING ONLY IF owner confirms (OWNER_DECISION #1). |

**Critical note:** B3/B4/B5 are blocking ONLY under the Treasure Chest's full
contract. Under the six-pillar public architecture (ADR-0008) they are NOT blocking.
This is OWNER_DECISION #1. The honest statement: per the Treasure Chest's own
status rule, the release is "NOT READY — BLOCKERS REMAIN" until B1/B2 are closed
and B3-B5 are either done or explicitly deferred by owner.

### STRONGLY RECOMMENDED (not contractually blocking, improves trustworthiness)

| Gap | Why recommended | Evidence |
|-----|-----------------|----------|
| S1. Batch 1 ATE cherry-pick | Adds gitleaks + release-security CI + MCP ATE; strengthens published artifact security posture. | BATCH1_CHERRYPICK_IMPACT.md; components/ absent in baseline |
| S2. Re-run full suite + 6-profile clean-install at final frozen SHA | doc 07 requires exact-SHA re-validation; earlier runs were pre-freeze. | doc 07 pre-freeze conditions |
| S3. KHSB encryption-profile tests | doc 10 requires secure-exchange tests before claiming KHSB security. | doc 10 required security properties |

### DOCUMENTATION REQUIRED (implementation exists, docs misleading/incomplete)

| Gap | Why required | Evidence |
|-----|--------------|----------|
| D1. CURRENT_STATE.md / RELEASE_STATE.md say `candidate_sha: UNFROZEN` | Contradicts frozen manifest (3888f08). Treasure Chest doc 00 forbids stale release decisions. | PUBLIC_DOC_TRUTH_AUDIT.md finding #1 |
| D2. SECURITY.md omits closure-pending status | Misleads on security readiness. | doc 07/08 |
| D3. CHANGELOG v0.4.1 refs unclear as historical | Minor confusion risk. | PUBLIC_DOC_TRUTH_AUDIT.md finding #2 |
| D4. Internal foundry capabilities (ClaimGuard/Governance/Bubble/SkillFoundry) undocumented as shipped | Users reading PUBLIC_API_STABILITY.md won't know they exist. Per spec, do NOT auto-promote to public tier, but a contributor note is warranted. | ARCHAEOLOGY_REVIEW.md |

### POST-V0_5 (excluded from blocking, listed for completeness)
- CRP runtime, Synchronization, Website/Launch, OUROBOROS, Reasoning sub-lobes,
  CAPTLANG, Whitepaper finalization, Codex corroboration re-run.

## Reconciliation with prior PUBLIC_RELEASE_GAP_REPORT.md

The earlier report (this review phase, prior turn) concluded "no blocking gaps."
That conclusion was scoped to the SIX-PILLAR public architecture and is NOW
SUPERSEDED for the full Treasure Chest contract. Per Phase 7 #3, the "no blocking
gaps" claim must be re-tested against the complete Treasure Chest — and it fails:
B1/B2 are blocking under doc 07, and B3-B5 are blocking if the owner confirms the
Treasure Chest's broader scope. The prior report's "Already present" rows (ClaimGuard
etc.) remain correct; only the "no blocking gaps" verdict is superseded.

## Verdict
- For the six-pillar public surface: implementation is complete and tests pass.
  The only gaps are D1-D4 (doc fixes) + S1-S3 (hardening/re-validation).
- For the full Treasure Chest v0.5 contract: B1/B2 are blocking; B3-B5 are
  owner-scope-dependent.
- Recommendation: close D1-D4 immediately (doc-only, no implementation), execute
  S1 (Batch 1 ATE) and S2 (re-validation), then resolve OWNER_DECISION #1 to
  determine whether B3-B5 are in scope. Do NOT publish/tag until B1/B2 closed or
  owner-accepted exception.
