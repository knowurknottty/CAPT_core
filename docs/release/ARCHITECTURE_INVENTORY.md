# ARCHITECTURE_INVENTORY — CAPT Core v0.5

Generated: 2026-07-30
Baseline: `integration/capt-v05-release-corrected` @ `be4b0da` (Python 3.12.13)
Evidence basis: import smoke test (all 14 subsystems import OK), dedicated test
modules present for 12/14, CLI exposure verified for evidence/verify/canon.

Scoring (1–10):
- Eng. Maturity: code completeness, test depth, internal integration.
- Release Readiness: docs, CLI surface, stability contract, validation gates.
- Risk: regression/complexity/coupling risk if changed before v0.5.

## Subsystem inventory

### Memory (`capt_solo/memory`) — 21 py
- Exists: YES | Stable: YES | Integrated: YES (28 internal importers) | Tested: YES (test_memory*.py, test_phase3c) | Documented: YES
- Eng 9 / Ready 8 / Risk 4
- Notes: largest, most-referenced subsystem. Deduplication, types, persistence.
  Low risk; core to v0.5.

### CTP (`capt_solo/ctp`) — 2 py
- Exists: YES | Stable: YES | Integrated: YES (4 importers) | Tested: YES (test_ctp.py) | Documented: NO (gap)
- Eng 7 / Ready 6 / Risk 5
- Notes: journal runtime. ATE branches carry CTP journal contract fixes
  (`9270986`, `d091c33`) NOT in baseline — candidate for cherry-pick.

### Evidence (`capt_solo/evidence`) — 13 py
- Exists: YES | Stable: YES | Integrated: YES (imported by continuity) | Tested: YES (test_evidence_*.py, 4 modules) | Documented: YES
- Eng 8 / Ready 8 / Risk 4
- Notes: Evidence Engine core, VSI integration, workspace isolation, proof graph.
  Strong test coverage. CLI exposes `evidence --status`, `verify run`.

### Verification (`capt_solo/verification`) — 6 py
- Exists: YES | Stable: YES | Integrated: YES | Tested: YES (test_verification_*.py, 4 modules) | Documented: YES
- Eng 8 / Ready 9 / Risk 3
- Notes: VSI, evidence integrity, routing. Recently hardened (6 security fixes
  in baseline). Highest release-readiness due to validation gates.

### Foundry (`capt_solo/foundry`) — 12 py
- Exists: YES | Stable: YES | Integrated: YES (self-consistent proof/registry/columns) | Tested: YES (test_v04_foundry.py) | Documented: NO (gap)
- Eng 7 / Ready 6 / Risk 5
- Notes: Proof Engine, registry, column codec. Proof graph + reuse. No top-level
  doc; internal integration solid.

### Knowledge (`capt_solo/knowledge`) — 3 py
- Exists: YES | Stable: YES | Integrated: YES (4 importers) | Tested: YES (test_phase3g) | Documented: YES
- Eng 7 / Ready 7 / Risk 4

### ContextPack (`capt_solo/contextpack`) — 2 py
- Exists: YES | Stable: YES | Integrated: YES (imported by continuity) | Tested: YES (test_contextpack_v1.py) | Documented: YES
- Eng 7 / Ready 7 / Risk 3
- Notes: deterministic ContextPack v1 integrity contract (from cve-v0.2 branch,
  absorbed into baseline).

### Continuity (`capt_solo/continuity`) — 5 py
- Exists: YES | Stable: YES | Integrated: YES (imports evidence) | Tested: YES (test_continuity_*.py) | Documented: YES
- Eng 7 / Ready 7 / Risk 4
- Notes: graph runtime, operational continuity. Imports evidence.providers.

### KHSB (`capt_solo/khsb`) — 1 py (bus.py)
- Exists: YES | Stable: YES (declared stable in manifest) | Integrated: YES (imported by core/config, memory/pipeline, plugin) | Tested: YES (test_khsb.py) | Documented: NO (gap)
- Eng 7 / Ready 7 / Risk 4
- Notes: Knowledge/Hermes bridge bus. Declared stable in PUBLIC_API_MANIFEST.
  Add a short doc page before v0.5.

### Engines (`capt_solo/engines`) — 4 py
- Exists: YES | Stable: PARTIAL | Integrated: YES (1 importer) | Tested: NO dedicated | Documented: NO
- Eng 5 / Ready 4 / Risk 6
- Notes: no dedicated test module. Importable but unverified in suite. Flag for
  owner review — either add tests or mark internal/experimental.

### Execution (`capt_solo/execution`) — 2 py
- Exists: YES | Stable: YES | Integrated: YES (1 importer) | Tested: YES (test_phase3h) | Documented: NO
- Eng 6 / Ready 5 / Risk 5

### Learning (`capt_solo/learning`) — 3 py
- Exists: YES | Stable: YES | Integrated: YES (2 importers) | Tested: YES (test_phase3j) | Documented: NO
- Eng 6 / Ready 5 / Risk 5

### Ontology (`capt_solo/ontology`) — 1 py
- Exists: YES | Stable: PARTIAL | Integrated: YES (1 importer) | Tested: NO dedicated | Documented: YES
- Eng 5 / Ready 4 / Risk 6
- Notes: single module, no dedicated test. Flag for review.

### Plugin (`capt_solo/plugin`) — 1 py
- Exists: YES | Stable: YES | Integrated: YES | Tested: YES (test_plugin*.py, 3 modules) | Documented: NO
- Eng 6 / Ready 6 / Risk 4
- Notes: plugin.json loader. Well-tested.

### Research (`capt_solo/research`) — 2 py
- Exists: YES | Stable: YES | Integrated: YES (1 importer) | Tested: YES (test_phase3k) | Documented: NO
- Eng 6 / Ready 5 / Risk 5

### Components (`capt_solo/components`) — ABSENT in baseline
- ATE component lives ONLY on hardening/* and integration/anti-token-extraction-v0.2
  branches (not merged). See BRANCH_CENSUS.md → Cherry-Pick.
- Eng (on branch): 7 / Ready (on branch): 7 / Risk (if merged): 5

## Cross-cutting capabilities (from owner's list)

| Capability | Status in baseline | Notes |
|------------|-------------------|-------|
| Memory | PRESENT (mature) | core |
| CTP | PRESENT (needs journal fix) | cherry-pick from ATE branches |
| Foundry / Proof Engine | PRESENT | proof graph, registry |
| ClaimGuard | NOT FOUND as module | may be conceptual; flag |
| Proof Engine | PRESENT (foundry.proof) | |
| Knowledge Bubble Runtime | NOT FOUND | likely conceptual; flag |
| Governance | NOT FOUND as module | flag |
| Capability Registry | PRESENT (foundry.registry) | |
| Workflow Proof | PARTIAL (foundry proof) | |
| Messaging | NOT FOUND | flag |
| API | PRESENT (capt_cli.py + public API manifest) | |
| Installer | PRESENT (pyproject + build) | |
| Diagnostics | PRESENT (doctor.sh, capt doctor) | |
| Validation | PRESENT (release_validation.py) | |
| Hermes Integration | PARTIAL (skill/plugin surface) | |
| Skills | PRESENT (plugin/skills) | |
| Schemas | PRESENT (schema identity checks) | |
| Migration | PARTIAL (no migration module found) | flag |
| Security | PRESENT (6 fixes + ATE on branch) | |
| Plugins | PRESENT | |
| MCP | PARTIAL (ATE branch has MCP adapter; baseline lacks) | cherry-pick candidate |

## Flagged for owner review (missing evidence)
- ClaimGuard, Knowledge Bubble Runtime, Governance, Messaging, Migration: no module
  found in baseline tree. Either conceptual/deferred, or misnamed. Do NOT remove;
  flag for owner decision.
- Engines, Ontology: importable but no dedicated test — add tests or mark internal.

## Release readiness verdict
12/14 subsystems are release-ready (tested + integrated + documented or internally
consistent). 2 (engines, ontology) need a test or explicit internal designation
before v0.5. ATE/MCP security hardening is the single highest-value addition
available via cherry-pick (see BRANCH_CENSUS.md).
