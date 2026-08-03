# CAPT Runtime M0 — Merge Plan

Date: 2026-08-03
Status: prepared, NOT executed (owner authorization required to merge).

## Chosen strategy: Strategy A — Merge stacked PRs in order (preserve proven SHAs)

### Rationale (compared options)

| Criterion | A (stacked merge) | B (integration branch) | C (rebase) | D (squash docs) |
|-----------|-------------------|------------------------|------------|-----------------|
| Auditability | high (linear history, proven SHAs) | medium (temp branch) | medium (SHAs rewritten) | low (history collapsed) |
| Commit provenance | preserved | preserved | lost (new SHAs) | partially lost |
| Conflict risk | low (clean ancestry) | low | medium (rebase churn) | low |
| Review clarity | high (one PR per layer) | medium | medium | low |
| Rollback simplicity | high (revert merge) | medium | low (rewritten) | low |
| Branch protection | compatible | compatible | risky (force-push) | policy-dependent |
| GitHub PR behavior | native stacked PRs | extra PR | retarget churn | changes PR diffs |
| Effect on cited SHAs/evidence | none | none | invalidates freeze docs' SHAs | invalidates evidence |
| Risk of invalidating verification | none | none | high (re-run needed) | medium |

**Recommendation: Strategy A.** The ancestry is already a clean linear stack
(main → M0-A → M0-B → freeze). No conflict, no divergence in implementation.
Rewriting history (C/D) would make every cited verification SHA (6665a6a,
0d851c4, f76b1cb) stale and force re-verification. Strategy B adds an unnecessary
temporary branch. Strategy A preserves provenance and keeps each layer reviewable.

## Merge order (owner-executed)

1. **M0-A → main.** Merge `feat/capt-runtime-m0a-contract-state-proof` (6665a6a)
   into `main`. This brings the architecture-spec docs + M0-A implementation.
   After merge: main contains M0-A.
2. **Close PR #21 as superseded.** Its 3 docs are now in main via M0-A. Do NOT
   merge #21 (would duplicate). Add a comment citing M0-A containment.
3. **M0-B → main.** Merge `feat/capt-runtime-m0b-readonly-driver-proof-hy3`
   (0d851c4) into main. PR #23 base (M0-A) is now satisfied.
4. **Post-M0-B review docs → main.** Merge `docs/post-m0b-governance-review`
   (80fd871) into main (after M0-B; acceptance evidence for M0-B).
5. **M0 freeze → main.** Merge `docs/capt-runtime-m0-freeze` (f76b1cb) into main.
   PR #24 base (M0-B) satisfied.
6. **M0 integration record → main.** Merge `docs/capt-runtime-m0-integration`
   (this branch) into main. PR #25 base (freeze) satisfied.

## Retargeting (non-destructive metadata only)

- PR #21: retarget base to `main` (current) OR close as superseded. No code change.
- PR #23 / #24 / #25: bases already correct (proven ancestors). No retarget needed.

## Verification gates after each merge

After each merge into main, rerun the smallest relevant smoke gate:
`pytest tests/capt_runtime/test_m0b_driver.py -q` (M0-B) and
`pytest tests/capt_runtime -q` (runtime). If counts diverge, stop.

## What must NOT enter main

- PR #21 (duplicate of M0-A).
- The parallel `capt-m0b` worktree branch (`c518acf`) — independent, not in stack.
- Any M0-C, RuntimeAggregate, RuntimeManifest, or external-driver code (none exists).

## Authorization boundary

This plan is prepared but **not executed**. The current instruction does not
contain explicit merge authorization. Per the mission's merge-authorization
boundary, all PRs are left ready and the process stops at
M0_STACK_READY_FOR_OWNER_MERGE until the owner authorizes merges.
