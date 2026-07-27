# CAPT_CANON — Workspace Entrypoint

This root file exists as the discoverable entrypoint required by the CAPT
Universal Workspace contract (see `AGENTS.md` and `WORKSPACE.md`). It is **not**
a duplicate of the constitutional architecture.

The full constitutional document — invariants I-01 through I-15, the ontology
(§4), layer definitions (§3), the canonical subsystem registry (§6), maturity
model (§7), public boundary (§8), compatibility policy (§9), and release
philosophy (§10) — lives at:

    docs/CAPT_CANON.md

## Why this split

`docs/CAPT_CANON.md` is referenced by `architecture/registry.yaml`, six ADRs
under `docs/adr/`, and `tests/test_architecture_fitness.py`. To avoid
duplication and drift, the single authoritative source remains there. This root
file is the pointer a newly-attached agent reads first.

## Invariant index (summary; full text in docs/CAPT_CANON.md §2)

- I-01 Local-first by default
- I-02 Evidence before assertion
- I-03 Deterministic where practical
- I-04 Explicit uncertainty
- I-05 Privacy-preserving defaults
- I-06 Modular cognition
- I-07 Bounded failure domains
- I-08 Backward-compatible public contracts
- I-09 Optional capabilities degrade independently
- I-10 Architecture drives implementation
- I-11 Implementation never silently redefines architecture
- I-12 Ontology is shared and upstream
- I-13 Canonical home is permanent unless re-canonicalized
- I-14 Forensic corpus is evidence, not authority
- I-15 Evidence over implementation (established by ADR-0006)

## Authority order (for any agent)

1. docs/CAPT_CANON.md (this constitution)
2. Approved architectural invariants (I-01..I-15)
3. architecture/registry.yaml
4. Approved ADRs (docs/adr/)
5. CANONICAL_ARCHITECTURE.md → docs/CANONICAL_ARCHITECTURE.md
6. CANONICAL_OWNERSHIP_MATRIX.md → docs/CANONICAL_OWNERSHIP_MATRIX.md
7. Current implementation contracts and tests
8. Implementation evidence (docs/evidence/, checkpoints/)
9. Historical and forensic materials

Existing code is implementation evidence, not automatic architectural authority.
Architecture governs implementation. Canon changes only through an explicit
architectural decision process (an ADR). Contradictions must be surfaced, not
silently reconciled.
