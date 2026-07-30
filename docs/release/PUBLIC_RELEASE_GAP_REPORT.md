# PUBLIC_RELEASE_GAP_REPORT — v0.5 Public Release Only

Generated: 2026-07-30
Scope: ONLY items that genuinely affect the quality, completeness, or correctness
of the PUBLIC CAPT Core v0.5 release. Research, future architecture, and
speculative enhancements are EXCLUDED (see IMPLEMENTATION_GAP_MATRIX.md for those).

## Verdict: no blocking gaps

Every capability in the public architecture (six-pillar + stable package list in
PUBLIC_API_MANIFEST_V0.5.json) is VERIFIED_IMPLEMENTED in the baseline tree
(`be4b0da`) and passes tests. The release validator (Option A) passes
(`ok: True`, 13/13 checks). The public release is internally consistent.

## Items that improve release quality (Nice to have, not Required)

| Item | Why it matters for the public release | Evidence | Disposition |
|------|---------------------------------------|----------|-------------|
| ATE components/ cherry-pick (Batch 1) | Adds MCP-based Anti-Token-Extraction + gitleaks + release-security CI. Strengthens the security posture of the published artifact. Public architecture depends on provider-neutrality/secret-clean behavior; the memory/antitoken.py already covers local, but components/ adds external-MCP interop. | components/ ABSENT in baseline; BATCH1_CHERRYPICK_IMPACT.md | Nice to have — owner approves Batch 1 |
| Public documentation for foundry submodules | ClaimGuard/Governance/Bubble/SkillFoundry are implemented (internal) but NOT in the public manifest's stable/experimental lists. A user reading PUBLIC_API_STABILITY.md would not know they exist. | foundry/* present; manifest omits foundry | Nice to have — doc update, not code |
| KHSB / Foundry / CTP doc pages | Declared stable in manifest but undocumented (ARCHITECTURE_INVENTORY flag). | manifest stable; no doc | Nice to have — Batch 2 docs |
| engines/ontology dedicated tests | engines + ontology import but lack dedicated tests; declared experimental/internal. | import OK, no test_v0* | Nice to have — Batch 3 |

## Items that are NOT gaps (clarification)

- ClaimGuard, Governance, Knowledge Bubbles, Skill Foundry, Proof Engine,
  Invention Engine: previously thought "missing/conceptual" — VERIFIED present
  in `capt_solo/foundry/` and `capt_solo/engines/`. No implementation needed.
- Proof Ledger: approximated by `governance_audit` table. Not required for v0.5
  public release (audit trail exists). Dedicated ledger is v0.5.1.
- Reasoning sub-lobes, CAPTLANG, OUROBOROS: research/external. Excluded from
  public release by design (CAPT_CANON research_package / external_package).

## Required-before-release check

| Public-architecture dependency | Implemented? | Evidence |
|-------------------------------|--------------|----------|
| Local-first memory (SQLite) | YES | memory/engine.py (1575 LOC), test_memory |
| CTP journal + receipts | YES | ctp/journal.py, test_ctp |
| KHSB bus | YES | khsb/bus.py, test_khsb |
| Hermes plugin (10 tools) | YES | plugin/__init__.py (808 LOC), test_plugin |
| Evidence + VSI verification | YES | evidence/, verification/, 4+ test modules |
| ClaimGuard (no false "verified") | YES | foundry/claimguard.py |
| Governance audit | YES | foundry/governance.py |
| Release validator (Option A) | YES | release_validation.py, 15 tests |
| Public API stability tiers | YES | PUBLIC_API_STABILITY.md + manifest |

All required public-architecture dependencies are present. **No required-before-
release gap exists.**

## Conclusion

The public v0.5 release is complete and internally consistent. The only
release-quality action recommended is the optional Batch 1 ATE cherry-pick
(security hardening) and the doc-page gaps (Batch 2). Neither blocks release.
Implementation work should NOT resume for the public release; it is feature-complete
per the public architecture.
