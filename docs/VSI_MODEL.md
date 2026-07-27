# Verified State Identity (VSI) — Verification Model

## Principle

> Verification is attached to the STATE being verified, not to the age of the
> conversation. A verification result stays valid while the Verified State
> Identity (VSI) remains equivalent. Conversation turns do not invalidate
> verification.

This resolves the "verification loop" inefficiency: repeatedly re-running the
identical test suite against an identical state produces no new evidence and
wastes engineering tokens. The VSI subsystem makes verification *state-bound*.

## Components

- **VerifiedStateIdentity** (`capt_solo/verification/identity.py`) — exact identity
  of the verified state: repository, project id, active branch, HEAD commit,
  scoped file hashes, dependency state, runtime identity, operating environment,
  verification command, verification scope. Two VSIs are equivalent iff all
  fields (except timestamp) match. `working_tree_status` (git porcelain) is kept
  for display but excluded from equivalence because it includes untracked
  artifacts (e.g. `.capt_verify/`, temp files) that are not part of the verified
  state.
- **VerificationScope** (`scope.py`) — FULL / SUITE / ENGINE_MATH / ENGINE_PHYSICS
  / ENGINE_INVENTION / MEMORY / BOUNDARY / DOCS / REGISTRY / WORKSPACE. Path→scope
  mapping drives targeted selection.
- **VerificationStatus** (`record.py`) — STATE_UNCHANGED, VERIFICATION_CURRENT,
  VERIFICATION_REQUIRED, VERIFICATION_PARTIAL, VERIFICATION_SUPERSEDED,
  VERIFICATION_INVALIDATED.
- **VerificationRecord / VerificationEvidence / VerificationPolicy** — persisted
  outcome, evidence pointer, and the reuse policy.
- **VerificationStore** (`store.py`) — append-only JSONL; records never mutated in
  place; superseded records are marked, not deleted.
- **VerificationEngine** (`engine.py`) — orchestrates: build VSI → compare to most
  recent compatible record → if equivalent, return VERIFICATION_CURRENT and reuse
  evidence (no rerun) → else identify exact diff reasons → select targeted scope
  → run only necessary verification → store new record (mark prior same-scope
  record superseded).

## Decision flow

1. Build current VSI.
2. `find_compatible(vsi)` → most recent record with equivalent VSI and not
   superseded.
3. If compatible and policy allows reuse → **VERIFICATION_CURRENT**; reuse
   evidence; explicitly report that re-running does NOT increase confidence.
4. If different → compute `diff_vsi(old, new)` reasons:
   - `head_changed` → full suite
   - `dependency_changed` → full suite
   - `environment_changed` → full suite
   - `scope_expanded` → run broader scope
   - `working_tree_changed` → run scopes of the changed files only
   - `command_changed` → run new command
   - `requested_by_user` (--force) → rerun
5. Run only the targeted scope. Documentation-only changes map to DOCS scope,
   which does not invoke the test suite.

## Confidence model

Confidence increases only when new evidence exists (state changed and was
re-verified). Repeating the identical verification against an identical VSI does
not increase confidence — the engine states this explicitly.

## CLI

```
python3 capt_cli.py verify run --scope engine_math [--force] [--command CMD]
python3 capt_cli.py verify status
```

The `verify` group is independent of the memory runtime and performs no network
I/O. Records persist under `.capt_verify/records.jsonl` (git-ignored; local-only).

## Long-mission optimization

For missions exceeding 444 reasoning turns, unnecessary verification is technical
debt. VSI ensures each verification is scoped to the changed state and reused
when unchanged, maximizing engineering progress per reasoning token without
reducing correctness.

## Tests

`tests/test_verification_vsi.py` (8 tests) demonstrate: unchanged-state reuse,
HEAD-change invalidation, dirty-tree invalidates only affected scopes,
documentation-only avoids full-suite, targeted selection, evidence reuse, no
verification loops, VSI equivalence/diff.
