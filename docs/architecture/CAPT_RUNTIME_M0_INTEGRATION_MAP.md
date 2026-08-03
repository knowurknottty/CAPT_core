# CAPT Runtime M0 — Integration Map

Date: 2026-08-03
Purpose: canonical integration graph for the M0 stack (architecture docs, M0-A,
M0-B, M0 freeze, post-M0-B review docs). Proven with Git ancestry, not branch names.

## Ancestry (proven via merge-base)

```
main (55e149b)
  └─ M0-A  feat/capt-runtime-m0a-contract-state-proof        (6665a6a)
       └─ M0-B  feat/capt-runtime-m0b-readonly-driver-proof-hy3 (0d851c4)
            └─ freeze  docs/capt-runtime-m0-freeze            (f76b1cb)
                 └─ integration  docs/capt-runtime-m0-integration (this branch)
```

Proof:
- `git merge-base --is-ancestor 6665a6a 0d851c4` → YES (M0-A in M0-B)
- `git merge-base --is-ancestor 0d851c4 f76b1cb` → YES (M0-B in freeze)
- `git merge-base --is-ancestor 6665a6a 55e149b` → NO (M0-A NOT yet in main)

## Layer table

| Layer | Branch | Head SHA | PR | Current base | Intended final destination | Status |
|-------|--------|----------|----|--------------|----------------------------|--------|
| Architecture specification | docs/capt-runtime-architecture-spec | 022f970 | #21 | main (e215a9e, **stale/divergent**) | main (via M0-A) | **SUPERSEDED** — content identical to M0-A |
| M0-A | feat/capt-runtime-m0a-contract-state-proof | 6665a6a | (none open; #23 targets M0-B) | — | main | ready |
| M0-B | feat/capt-runtime-m0b-readonly-driver-proof-hy3 | 0d851c4 | #23 | M0-A (6665a6a) | main (via M0-A) | ready, DRAFT |
| M0 freeze | docs/capt-runtime-m0-freeze | f76b1cb | #24 | M0-B (0d851c4) | main (via M0-B) | ready, DRAFT |
| Post-M0-B review docs | docs/post-m0b-governance-review | 80fd871 | (none open) | — | main (after M0-B) | ready |
| M0 integration record | docs/capt-runtime-m0-integration | (this) | #25 (proposed) | freeze (f76b1cb) | main (via freeze) | ready, DRAFT |

## PR inventory

| PR | State | Draft | Mergeable | Base | Head | Notes |
|----|-------|-------|-----------|------|------|-------|
| #21 | OPEN | yes | MERGEABLE | main (e215a9e) | docs/capt-runtime-architecture-spec (022f970) | **Superseded by M0-A**; base divergent from current main (55e149b) |
| #23 | OPEN | yes | MERGEABLE | M0-A | (M0-B) | correct base |
| #24 | OPEN | yes | MERGEABLE | M0-B | freeze | correct base |
| #25 | (proposed) | yes | — | freeze | integration | this record |

## Branch-graph analysis (findings)

- **Duplicated commits:** none in implementation. PR #21's architecture-spec branch
  (022f970) has **zero commits** not already in M0-A; its 3 docs are byte-identical
  to M0-A's. Merging #21 would duplicate architecture docs into main.
- **Divergent commits:** PR #21 base `e215a9e` is NOT an ancestor of current main
  `55e149b` → stale/divergent base. Does not affect content (already in M0-A).
- **Orphaned documentation:** none. All docs are reachable from M0-A or the
  review-doc branch.
- **Branch collisions:** none. Canonical M0-B name `feat/capt-runtime-m0b-...-hy3`
  coexists with the parallel worktree branch `feat/capt-runtime-m0b-...` (capt-m0b
  worktree, `c518acf`); they are separate and not merged.
- **Stale PR bases:** PR #21 only. PR #23/#24 bases are correct (proven ancestors).
- **Commits to rebase/cherry-pick:** none required. No history rewrite needed.
- **Commits that should NOT enter main:** PR #21 (duplicate of M0-A). Close as
  superseded after M0-A merges. The parallel `capt-m0b` worktree branch
  (`c518acf`) is independent and not part of this stack.

## PR #21 disposition

PR #21's three documents (CAPT_RUNTIME_ARCHITECTURE_SPEC.md,
CAPT_RUNTIME_TRIPLE_RECURSION_LEDGER.md,
CAPT_RUNTIME_CONTRACTS_AND_M0_IMPLEMENTATION_WORKFLOW.md) are **already contained
in M0-A** (byte-identical). They will enter main when M0-A merges. PR #21 should
be **closed as superseded** (not merged, not deleted) once M0-A is integrated, to
avoid duplicating the architecture docs. Its historical existence is preserved.

## Review-doc branch placement

The six post-M0-B documents on `docs/post-m0b-governance-review` are acceptance /
evidence / deferred-decision memos. They belong in main as part of the M0-B proof
record. Integration order: merge them into main **after M0-B** (they reference
M0-B acceptance). They are documentation-only and carry no implementation risk.
