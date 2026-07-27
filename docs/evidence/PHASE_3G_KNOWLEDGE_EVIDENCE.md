# Phase 3G — Knowledge / Evidence / Trust / Proof / Governance Convergence

**Branch:** integration/full-public-architecture
**Date:** 2026-07-26
**Issue:** #5
**Preceded by:** Phase 3F (commit 8886e0f)

## Objective
Converge the five Layer 3 subsystems — Knowledge, Evidence, Trust, Proof,
Governance — onto one canonical storage/interface foundation, satisfying I-02
(evidence before assertion) and I-12 (no duplicate definitions).

## What existed (canonical, preserved)
- `capt_solo/memory/trust.py` — deterministic trust engine (explicit auditable
  inputs; allowed-state transitions; never silent promotion). Preserved as-is.
- `capt_solo/foundry/proof.py` — ProofEngine + Evidence/ProofRequirement/
  ProofAggregate (deterministic, reproducible). Preserved as-is.
- `capt_solo/foundry/governance.py` — Governance + GovernanceReceipt (immutable,
  auditable). Preserved as-is.

## What was added (canonical, new)
- `capt_solo/knowledge/evidence.py` — `EvidenceStore`: first-class evidence ledger
  (claim, source_refs, provenance, confidence, verification status, contradiction
  linkage). Backed by MemoryEngine (namespace `evidence`), reuses canonical fields.
  `to_ontology()` bridges to the Layer 0.5 `Evidence` term (single mapping, I-12).
- `capt_solo/knowledge/knowledge.py` — `KnowledgeStore`: knowledge bubbles (portable
  verifiable packages) linked to evidence + trust state. **Verification is gated**:
  `promote_status(VERIFIED)` refuses unless at least one linked evidence record is
  CORROBORATED or VERIFIED (I-02 enforced in code, not just docs).
- `capt_solo/knowledge/__init__.py` — convergence package re-exporting the new
  stores and documenting how Trust/Proof/Governance plug into the same foundation.

## Convergence properties (verified by tests)
- Evidence promotes claims; knowledge is never silently verified without
  corroborating evidence.
- Trust/Proof/Governance remain canonical and unchanged (no silent redefinition,
  I-11).
- All new stores reuse MemoryEngine + ontology types (I-12).

## Tests added
`tests/test_phase3g_knowledge_evidence.py` (7):
- evidence add + status transition
- evidence contradiction linkage (both directions)
- knowledge REQUIRES corroborating evidence to verify (I-02 enforced)
- knowledge status progression (hypothesis -> supported)
- evidence -> ontology bridge
- list filtering by status
- export/import round-trip

## Verification
- `pytest`: 430 passed (was 423).
- `verify_runtime.py`: 46/46 pass (unchanged).

## Result
Knowledge/Evidence are now canonical, tested, and converged with the existing
Trust/Proof/Governance engines on one foundation. Ready for Phase 3H
(Skills / Execution hardening).
