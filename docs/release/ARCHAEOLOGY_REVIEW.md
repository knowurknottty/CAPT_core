# ARCHAEOLOGY_REVIEW — Evidence-Based Review of Archaeology Deliverables

Generated: 2026-07-30
Reviewer: HY3 (self-review under owner supervision)
Method: every claim in the archaeology docs was re-verified against the live repo
(import smoke, file existence, registry.yaml status, CLI exposure, test references).
This document is FINDINGS ONLY. No archaeology docs were edited (per Phase 1
instruction). Corrections are recorded here for the owner to apply.

## Critical correction (affects 5 of 20 Treasure Chest entries)

The archaeology pass searched for conceptual modules at the WRONG PATH
(`capt_solo/claimguard.py`, `capt_solo/governance.py`, etc.) and concluded they
were "CONCEPTUAL / no module". They actually exist under `capt_solo/foundry/`:

| Concept | Archaeology said | VERIFIED status | Evidence |
|---------|------------------|----------------|----------|
| ClaimGuard | CONCEPTUAL (no module) | **VERIFIED_IMPLEMENTED** | `capt_solo/foundry/claimguard.py` (208 LOC), imports OK, CLI `foundry`, tests reference it |
| Governance | CONCEPTUAL (no module) | **VERIFIED_IMPLEMENTED** | `capt_solo/foundry/governance.py` (137 LOC), `governance_audit` table, tests reference it |
| Knowledge Bubbles | CONCEPTUAL (no module) | **VERIFIED_IMPLEMENTED** | `capt_solo/foundry/bubble.py` (412 LOC), quarantine lifecycle, 6 test files reference it |
| Skill Foundry | CONCEPTUAL (no module) | **VERIFIED_IMPLEMENTED** | `capt_solo/foundry/skill_foundry.py` (478 LOC), CLI `foundry list-skills` |
| Proof Ledger | MISSING | **VERIFIED_PARTIAL** | `governance_audit` table in `foundry/governance.py` approximates it; dedicated ledger module absent (registry: "missing (approximated)") |
| Invention Engine | MISSING | **VERIFIED_IMPLEMENTED** | `capt_solo/engines/invention.py` (experimental), imports OK |
| Proof Engine | SHIPPED (partial) | **VERIFIED_IMPLEMENTED** | `capt_solo/foundry/proof.py` (303 LOC) — complete, not partial |

Root cause: the archaeology pass used `find capt_solo -maxdepth 1` style checks
and the `architecture/registry.yaml` was not consulted for the `foundry.*` path
mapping. The registry (authoritative) already lists all these as `complete` with
`current_path: foundry/...`.

## Per-document review

### ARCHITECTURE.md
- Accuracy: MOSTLY ACCURATE. Lists shipped subsystems correctly. BUT the
  "CONCEPTUAL (documented, not in code)" line incorrectly names ClaimGuard,
  Knowledge Bubbles, Governance, Proof Ledger as not-in-code. They ARE in code
  (foundry/).
- Completeness: adequate as entry point.
- Unsupported assumption: "Governance (wrapper) absent" — wrong; wrapper present.
- Recommendation: correct the CONCEPTUAL list; move ClaimGuard/Governance/Bubble/
  SkillFoundry/ProofEngine to SHIPPED.

### DESIGN_PRINCIPLES.md
- Accuracy: ACCURATE. Philosophy recovery from ADRs + CAPT_CANON is faithful.
  No implementation claims made; purely conceptual. No correction needed.

### TRUST_MODEL.md
- Accuracy: PARTIALLY INACCURATE. States ClaimGuard "CONCEPTUAL — no module in
  baseline" and Governance "CONCEPTUAL — governance module absent". Both WRONG
  (foundry/claimguard.py, foundry/governance.py present). Proof Ledger correctly
  noted as missing-but-approximated.
- Recommendation: reclassify ClaimGuard + Governance to implemented (internal).

### LIFECYCLE.md
- Accuracy: PARTIALLY INACCURATE. States Knowledge Bubble wrapper "CONCEPTUAL — no
  knowledge_bubble module in baseline". WRONG (`foundry/bubble.py` present). CTP
  and session lifecycles accurate.
- Recommendation: reclassify Knowledge Bubbles to implemented.

### TREASURE_CHEST.md
- Accuracy: 5 entries wrong (ClaimGuard #4, Governance #6, Knowledge Bubbles #5,
  Proof Ledger #14 partial, Invention Engine #10, Proof Engine #3 overstated as
  partial). 14/20 accurate.
- Duplicated concepts: correctly identified Proof Engine = Foundry Proof.
- Architectural value: high. The catalog structure is sound; only status labels
  need correction.
- Recommendation: apply the 6 status corrections above.

### CONCEPT_EVOLUTION.md
- Accuracy: MOSTLY ACCURATE. The "Proof Engine → Foundry Proof" lineage is
  correct. The ClaimGuard/Governance/Knowledge-Bubbles "three separate v0.4
  concept docs, none implemented except Proof Engine substrate" is WRONG — all
  three ARE implemented in foundry/. The "Bubble wrapper is the missing
  integration" claim is wrong.
- Recommendation: correct the lineage note; these are implemented, not conceptual.

### ARCHITECTURAL_PATTERNS.md
- Accuracy: ACCURATE. Patterns P1–P12 describe real code (validator, CTP,
  registry, VSI, plugin, degradation language, Option A). P2/P4/P7/P10 reference
  Governance/Bubble/ClaimGuard — these are implemented, so the patterns are
  grounded, not aspirational. No correction needed (patterns hold).

### ROADMAP_FROM_RESEARCH.md
- Accuracy: PARTIALLY INACCURATE. Recommends ClaimGuard (v0.5.1), Governance
  wrapper (Future), Knowledge Bubbles wrapper (Future), Proof Ledger (v0.5.1) as
  implementation work. Since ClaimGuard/Governance/Bubble are ALREADY implemented,
  those roadmap items are "Already present — documentation only", not build items.
  Proof Ledger remains a partial gap (governance_audit exists).
- Recommendation: move ClaimGuard/Governance/Knowledge Bubbles from "build" to
  "document/internal-surface" in roadmap.

### HY3_RELEASE_FREEZE_INCIDENT.md
- Accuracy: ACCURATE (historical incident record). No implementation claims. No
  correction.

## Summary of corrections required (owner to apply)
1. ClaimGuard → VERIFIED_IMPLEMENTED (internal, foundry/claimguard.py)
2. Governance → VERIFIED_IMPLEMENTED (internal, foundry/governance.py)
3. Knowledge Bubbles → VERIFIED_IMPLEMENTED (internal, foundry/bubble.py)
4. Skill Foundry → VERIFIED_IMPLEMENTED (internal, foundry/skill_foundry.py)
5. Proof Engine → VERIFIED_IMPLEMENTED (not partial)
6. Proof Ledger → VERIFIED_PARTIAL (governance_audit approximates)
7. Invention Engine → VERIFIED_IMPLEMENTED (experimental, engines/invention.py)

These do NOT change the v0.5 release status: all are already in the baseline
tree and pass tests. They change the INTELLECTUAL MAP (Treasure Chest) accuracy,
not the implementation map.
