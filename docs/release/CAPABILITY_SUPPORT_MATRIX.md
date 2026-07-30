# CAPABILITY_SUPPORT_MATRIX — CAPT Core v0.5

Generated: 2026-07-30
Cross-repo evidence: CAPT_core (baseline cdc1bcc), backup (a04b6fc, subset),
Treasure Chest (docs 00-17). Status vocabulary per review spec.

Status key: VPS=VERIFIED_PUBLIC_SUPPORTED, VI=VERIFIED_INTERNAL, VE=VERIFIED_EXPERIMENTAL,
VP=VERIFIED_PARTIAL, BO=BACKUP_ONLY, DNI=DOCUMENTED_NOT_IMPLEMENTED, SUP=SUPERSEDED,
RE=RESEARCH_OR_EXTERNAL, OD=OWNER_DECISION

| Capability | Pillar | Pkg tier | Impl location | Runtime wiring | CLI | Tests | Docs | Security ev | Release ev | Unique backup | Treasure Chest req | Status | Action |
|-----------|--------|----------|---------------|-----------------|-----|-------|------|------------|-----------|---------------|-------------------|--------|--------|
| Memory | 1/3 | stable | memory/engine.py | yes | memory cmd | test_memory | ARCHITECTURE | n/a | yes | no | doc01/02 | VPS | keep |
| ContextPack | 4 | stable | contextpack/core.py | yes | capt pack | test_contextpack | PUBLIC_ARCH | n/a | yes | no | doc02 | VPS | keep |
| Evidence Engine | 2 | stable | evidence/ | yes | verify | 4 test mods | EVIDENCE_MODEL | n/a | yes | no | doc01/02 | VPS | keep |
| VSI | 2 | stable | verification/identity.py | yes | release validate | test_vsi | VSI_MODEL | n/a | yes | no | doc01 | VPS | keep |
| Proof Engine | 2/5 | internal | foundry/proof.py | yes | foundry | test_foundry | PROOF_ENGINE | n/a | yes | no | doc01 | VI | keep |
| ClaimGuard | 5 | internal | foundry/claimguard.py | yes | foundry | tests ref | CLAIMGUARD | n/a | yes | no | doc01 | VI | keep (was mislabeled) |
| Governance | 8 | internal | foundry/governance.py | yes | foundry | tests ref | GOVERNANCE | governance_audit | yes | no | doc01 | VI | keep |
| Knowledge Bubbles | 4 | internal | foundry/bubble.py | yes | foundry | 6 test files | KNOWLEDGE_BUBBLES | quarantine | yes | no | doc01 | VI | keep |
| Skill Foundry | 9 | internal | foundry/skill_foundry.py | yes | foundry | test_foundry | SKILL_FOUNDRY | n/a | yes | no | doc01 | VI | keep |
| CSG | 3 | stable | memory/csg.py | yes | n/a | test_csg | ARCHITECTURE | n/a | yes | no | doc01 | VPS | keep |
| CTP | 6 | stable | ctp/journal.py | yes | n/a | test_ctp | CANONICAL | receipts | yes | no | doc10 | VPS | keep |
| KHSB | 4 | stable | khsb/bus.py | yes | n/a | test_khsb | ARCHITECTURE | partial | yes | no | doc10 | VPS | keep (encrypt tests missing) |
| CRP roadmap | 6 | n/a | (deferred) | n/a | n/a | n/a | doc10 | n/a | n/a | no | doc10/03 | DNI (POST_V0_5) | defer |
| Lifecycle | 6 | stable | lifecycle/ | yes | n/a | test_lifecycle | ARCHITECTURE | n/a | yes | no | doc01 | VPS | keep |
| Plugin/Hermes | 9/11 | stable | plugin/__init__.py | yes | n/a | test_plugin | PLUGIN_GUIDE | n/a | yes | no | doc01 | VPS | keep |
| Anti-Token-Extraction | 3 | stable | memory/antitoken.py | yes | n/a | test_antitoken | ARCHITECTURE | fidelity guards | yes | NO (components/ absent) | doc09 | VP (local only) | cherry-pick components/ (Batch 1) |
| Capability Registry | 5 | internal | architecture/registry.yaml | validate_registry | n/a | n/a | CAPABILITY_REGISTRY | n/a | yes | no | doc01 | VI | keep |
| Invention Engine | 2 | experimental | engines/invention.py | yes | n/a | n/a | (none) | n/a | partial | no | doc01 | VE | keep (was mislabeled missing) |
| Ontology | 0.5 | experimental | ontology/__init__.py | yes | n/a | no dedicated | ADR-0002 | n/a | partial | no | doc01 | VE | add test |
| Engines | 2 | experimental | engines/ | yes | n/a | partial | ARCHITECTURE | n/a | partial | no | doc01 | VE | keep |
| Learning | 10 | experimental | learning/ | yes | n/a | test_continuous | ARCHITECTURE | n/a | partial | no | doc01 | VE | keep |
| Synchronization | 3 | n/a | (none) | n/a | n/a | n/a | doc13 | n/a | no | no | doc03 (deferred) | DNI (POST_V0_5) | defer |
| Migration | 3 | stable | migration/ | yes | n/a | test_migration | ARCHITECTURE | n/a | yes | no | doc01 | VPS | keep |
| Proof Ledger/IMMU | 5 | internal | governance_audit (approx) | partial | n/a | n/a | TREASURE | partial | partial | no | doc01 | VP | v0.5.1 extract |
| Trust/Privacy/Compliance | 5/8 | n/a | (docs only) | n/a | n/a | n/a | doc08 | NO final | no | no | doc08 | DNI (MISSING_RELEASE_REQ) | Trust Center required |
| Release validation | 8 | stable | release_validation.py | yes | capt release validate | 15 tests | CANDIDATE_FREEZE | n/a | yes (Option A) | no | doc02/07 | VPS | keep frozen |
| Security CI | n/a | n/a | (none in baseline) | n/a | n/a | n/a | doc04 | NO | no | NO (backup lacks) | doc04 | DNI (MISSING_RELEASE_REQ) | Batch 1 adds gitleaks+CI |
| Packaging/Install | n/a | stable | pyproject, wheel | yes | capt | wheel tests | doc02 | n/a | yes | no | doc02/07 | VPS | rerun at final SHA |
| CLI/DX | n/a | stable | capt_cli.py | yes | capt | test_cli | CLI.md | n/a | yes | no | doc01 | VPS | keep |
| Website/Public Launch | n/a | n/a | (none) | n/a | n/a | n/a | doc12 | n/a | no | no | doc12 | DNI (POST_V0_5) | defer per release rules |
| **Space architecture** | n/a | n/a | (none) | n/a | n/a | n/a | doc15-D | n/a | no | no | doc15-D | DNI (MISSING_RELEASE_REQ) | OWNER_DECISION #1 |
| **Provider-neutral runtime adapter** | n/a | n/a | research/adapter.py (partial) | partial | n/a | n/a | doc15-E | n/a | no | no | doc15-E | VP (MISSING_RELEASE_REQ) | OWNER_DECISION #1 |
| **Trust Center / Threat Model / SBOM** | n/a | n/a | (none) | n/a | n/a | n/a | doc15-F | n/a | no | no | doc15-F | DNI (MISSING_RELEASE_REQ) | OWNER_DECISION #1 |

## Notes
- "Unique backup" column is NO for all rows: the backup (a04b6fc) is a strict
  ancestor subset; it adds no unique capability evidence.
- ATE components/ is the only capability whose best evidence lives OUTSIDE the
  baseline (on origin hardening/* branches), captured in BATCH1_CHERRYPICK_IMPACT.md.
- The three OWNER_DECISION #1 rows (Space, runtime adapter, Trust Center) are the
  Treasure Chest's broader v0.5 contract not met by the six-pillar surface.
