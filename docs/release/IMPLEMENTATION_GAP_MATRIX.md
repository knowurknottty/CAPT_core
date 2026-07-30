# IMPLEMENTATION_GAP_MATRIX — Recovered Concepts vs Repository

Generated: 2026-07-30
Evidence basis: live repo inspection (file existence, import smoke, registry.yaml
status, CLI exposure, test references). Status vocabulary per review spec.

Legend:
VI=VERIFIED_IMPLEMENTED  VP=VERIFIED_PARTIAL  IAN=IMPLEMENTED_UNDER_ANOTHER_NAME
DO=DOCUMENTED_ONLY  FBD=FUTURE_BY_DESIGN  RO=RESEARCH_ONLY  OB=OBSOLETE  OD=OWNER_DECISION

| # | Recovered concept | Current implementation | Evidence | Status | Release impact | Recommendation |
|---|-------------------|------------------------|----------|--------|----------------|---------------|
| 1 | VSI | capt_solo/verification/identity.py (211 LOC) | import OK, test_verification_vsi.py | VI | Already present | Keep |
| 2 | Evidence Engine | capt_solo/evidence/ (core 202 LOC) | import OK, 4 test modules | VI | Already present | Keep |
| 3 | Proof Engine | capt_solo/foundry/proof.py (303 LOC) | import OK, test_v04_foundry.py | VI | Already present | Keep (was mislabeled partial) |
| 4 | ClaimGuard | capt_solo/foundry/claimguard.py (208 LOC) | import OK, CLI foundry, tests ref | VI | Already present | Keep (was mislabeled conceptual) |
| 5 | Knowledge Bubbles | capt_solo/foundry/bubble.py (412 LOC) | import OK, 6 test files ref | VI | Already present | Keep (was mislabeled conceptual) |
| 6 | Governance | capt_solo/foundry/governance.py (137 LOC) + governance_audit | import OK, tests ref | VI | Already present | Keep (was mislabeled conceptual) |
| 7 | Anti-Token-Extraction | memory/antitoken.py (273 LOC) + components/ (ABSENT) | import OK; components/ absent | VP | Cherry-pick candidate | Cherry-pick components/ (Batch 1) |
| 8 | CSG | memory/csg.py (375 LOC) | import OK, test_v02_csg.py | VI | Already present | Keep (registry path mismatch noted) |
| 9 | ContextPack v1 | contextpack/core.py (310 LOC) | import OK, test_contextpack_v1.py | VI | Already present | Keep |
| 10 | Invention Engine | engines/invention.py | import OK (experimental) | VI | Already present (experimental) | Keep; was mislabeled missing |
| 11 | Skill Foundry | foundry/skill_foundry.py (478 LOC) | import OK, CLI foundry | VI | Already present | Keep (was mislabeled conceptual) |
| 12 | Reasoning sub-lobes (CIG/HDR/META/CONSC/QIPC/RYS/NEDA) | none in capt-solo | registry: missing, biocapt-ecosystem | RO | Research | Owner PORT-or-exclude |
| 13 | CAPTLANG | external (Biocapt-ecosystem-fullcaptlang) | not in capt-solo | OD | External package | Exclude from core |
| 14 | Proof Ledger / IMMU | governance_audit table approximates; no dedicated ledger | registry: missing (approximated) | VP | Post-release | v0.5.1: extract ledger from governance |
| 15 | OUROBOROS / Continuous Learning | learning/continuous.py (partial) | import OK, test_phase3j | VP | Already present (partial) | Add tests; mark internal |
| 16 | PULSE LLM gateway | pulse.py (complete, experimental) | import OK, optional_plugin | VI | Already present (optional) | Owner [S] decision |
| 17 | Release Validator (Option A) | release_validation.py (frozen) | import OK, 15 tests pass | VI | Already present | Keep frozen |
| 18 | Six-Pillar Public Architecture | PUBLIC_ARCHITECTURE.md + manifest | docs present | VI | Already present | Keep |
| 19 | Capability Registry | architecture/registry.yaml (70 caps) | validate_registry.py | VI | Already present | Keep |
| 20 | Degradation-Aware Language | foundry/claimguard.py + memory/antitoken.py | implemented | VI | Already present | Keep |
| 21 | Autobiographical Memory | none | registry: missing | DO/FBD | Future | Design only |
| 22 | Synchronization | none (bubbles are portability, not sync) | registry: missing/planned | FBD | Future | v0.6+ |
| 23 | Skill Radar | none (merged into Foundry) | registry: missing | IAN | Already present (in Foundry) | None |
| 24 | HMC / ENGRAM / DREAM | memory/hmc.py, memory/engram.py, learning/dream.py | present (research maturity) | VP | Already present (research) | Keep as research |
| 25 | Consent | memory/consent.py (local consent ledger) | present | VI | Already present | Keep |

## Key corrections vs archaeology docs
- ClaimGuard/Governance/Knowledge Bubbles/Skill Foundry: were "CONCEPTUAL", now
  VI (implemented in foundry/).
- Proof Engine: was "partial", now VI.
- Invention Engine: was "MISSING", now VI (experimental).
- Proof Ledger: was "MISSING", now VP (governance_audit approximates).
- Skill Radar: was implied missing, now IAN (merged into Foundry).

## Genuinely missing (evidence-confirmed)
- Reasoning sub-lobes (CIG/HDR/META/CONSC/QIPC/RYS/NEDA) — RO, owner decision.
- Autobiographical Memory — DO/FBD.
- Synchronization — FBD.
- CAPTLANG — OD (external).
- Dedicated Proof Ledger module — VP (approximated by governance_audit).

## Release-critical gaps (affect v0.5 public quality)
- NONE blocking. All public-architecture-dependent capabilities (VSI, Evidence,
  Proof, ClaimGuard, Governance, Bubbles, CTP, KHSB, Foundry, CLI, Plugin) are
  VERIFIED_IMPLEMENTED in the baseline.
- The only release-relevant action is the ATE components/ cherry-pick (Batch 1),
  which adds MCP-based token handling + secret scanning CI (security hardening,
  not a missing public capability).
