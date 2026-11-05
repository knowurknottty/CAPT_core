---
status: Proposed (recommendation only — no implementation)
date: 2026-08-03
relates_to: ADR-0130
---

# ADR-0131 — Canonical architecture reconciliation (future process)

## Status note

**This record is a recommendation only.** It defines a future process. It
authorizes no code change, no branch merge, no cherry-pick, and no history
repair. It was produced as a by-product of the Foundry M0 boundary exercise and
is recorded so the finding is not lost.

## Context

Boundary verification at `5fb323d6edd8511b687eaec9f6656fc4b4d0b320` established,
against Git object state rather than worktree appearance, that
`knowurknottty/CAPT_core` currently carries **two divergent architectural
lineages**.

### Lineage A — runtime-centric (`origin/main`, the authoritative base)

- Governance: `docs/architecture/decisions/ADR-0101…ADR-0127` (19 Accepted records).
- Implementation: `capt_runtime/` — aggregates, services, transactional store,
  event ledger, outbox, replay, checkpoint, drivers.
- Contracts: `contracts/schema/*.json` with generated Python and TypeScript
  bindings and a drift check.
- Verified state at `5fb323d`: **469 passed, 44 skipped**.

### Lineage B — foundry-centric (unmerged)

Present on `origin/integration/capt-v05-final-audit`,
`origin/integration/capt-v05-release-corrected`,
`origin/release/capt-v05-layer-reconciliation`,
`origin/audit/independent-602dc5a`, `origin/feature/capt-bootstrap-bridge`,
`origin/feature/hermes-capt-core-runtime-skill`.

- Governance: `architecture/registry.yaml` (70 canonical subsystems), `AGENTS.md`,
  `CAPT_CANON.md`, `CANONICAL_OWNERSHIP_MATRIX.md`.
- Implementation: `capt_solo/evidence/` (~1,829 LOC: `ProofGraph`,
  `InvalidationGraph`, `EvidenceRecord`, promotion, invalidation, checkpoint),
  introduced by `5c9c807373ce1881f5afa8be01da86398f55e390`.

### The divergence

`capt_solo/foundry/`, `capt_solo/memory/`, and `capt_solo/lifecycle/` exist on
**both** lineages. `capt_runtime/` exists only on A. `capt_solo/evidence/` and
the registry canon exist only on B.

Consequence: **a subsystem's canonical status depends on which ref is read.**
`architecture/registry.yaml` marks Evidence Engine `complete` at
`capt_solo/evidence` — true on B, false on A, where the path does not exist.
The registry also names `capt_solo.memory.semantic` while the implementation is
`capt_solo/lifecycle/semantic.py`.

An agent or engineer reading canon from B and implementing against A will build
duplicates of subsystems that appear canonical but are absent. The Foundry M0
boundary exercise caught exactly this: three of nine originally proposed
capabilities were already satisfied on A, and the "missing" Evidence Engine that
Lineage B declares complete is not present on A at all.

## Recommended future process (not authorized here)

1. **Freeze the question.** Declare which lineage is authoritative for each
   subsystem, in writing, before any merge attempt. Do not resolve by merging and
   observing what survives.
2. **Produce a per-subsystem ownership table** with, for every subsystem:
   declared path, existence at the candidate SHA on each lineage, test presence,
   and measured maturity. Object state only — never worktree appearance.
3. **Classify each divergence** as: registry stale, implementation missing from
   remote, implementation exists only on an unmerged branch, implementation
   renamed, or unresolved.
4. **Choose one governance artifact.** Either the `ADR-01xx` series absorbs the
   registry, or the registry becomes canonical and references the ADRs. Two
   parallel governance structures is the root defect; ADR-0130 deliberately did
   not create a third.
5. **Land in dependency order**, smallest defensible increments, each with its
   own verification gate and a green full suite.
6. **Re-verify frozen proofs.** M0-A and M0-B proof branches must be re-run after
   any lineage merge; their evidence is only valid against the tree that produced
   it.
7. **Record the reconciliation** as a new Accepted ADR that supersedes this one.

## Explicit non-goals

- Not a merge plan and not an authorization to merge.
- Not a judgement that either lineage is wrong; both carry real, tested work.
- Not a Foundry concern. ADR-0130 records the discrepancy and builds only on
  Lineage A. Repairing lineage divergence during a feature effort would enlarge
  an implementation task into an unbounded governance one.

## Consequences of deferring

- New work on `main` cannot rely on `capt_solo/evidence/`.
- Lineage B accumulates further divergence while unmerged.
- Every future boundary exercise must repeat this Git-object verification.

## Reversal conditions

Superseded by the reconciliation ADR produced in step 7.
