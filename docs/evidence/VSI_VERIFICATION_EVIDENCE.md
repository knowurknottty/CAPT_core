# VSI_VERIFICATION_EVIDENCE.md

- **scope**: Verified State Identity (VSI) verification subsystem — reusable CAPT engineering capability (not repository-specific).
- **source_commit**: `d355c74` (parent of this milestone commit)
- **milestone**: VSI Optimization Pass

## Implemented
- `capt_solo/verification/identity.py` — `VerifiedStateIdentity`, `build_vsi`,
  `vsi_equivalent`, `diff_vsi`, `VsiDiffReason`. Equivalence excludes
  `working_tree_status` (git porcelain) because it includes untracked artifacts
  (`.capt_verify/`, temp files) not part of the verified state. Equivalence is
  driven by scoped file hashes + HEAD + dependency + environment + command + scope.
- `capt_solo/verification/scope.py` — `VerificationScope` enum, `SCOPE_PATH_GLOBS`
  (path→scope mapping), `map_paths_to_scopes`, `select_scope_for_changes`,
  `command_for_scope`. Documentation-only changes map to DOCS (no test suite).
- `capt_solo/verification/record.py` — `VerificationStatus` (STATE_UNCHANGED,
  VERIFICATION_CURRENT, VERIFICATION_REQUIRED, VERIFICATION_PARTIAL,
  VERIFICATION_SUPERSEDED, VERIFICATION_INVALIDATED), `VerificationRecord`,
  `VerificationEvidence`, `VerificationPolicy`.
- `capt_solo/verification/store.py` — append-only JSONL `VerificationStore`;
  records never mutated in place; `latest_for_scope` + `find_compatible` +
  `mark_superseded` (marks only the prior SAME-SCOPE record, not the global latest,
  so different scopes remain independently reusable).
- `capt_solo/verification/engine.py` — `VerificationEngine`: build VSI → compare to
  most recent compatible record → if equivalent return VERIFICATION_CURRENT and
  reuse evidence (no rerun, explicit "confidence does not increase" note) → else
  identify exact diff reasons → select targeted scope → run only necessary
  verification → store new record (supersede prior same-scope). First verification
  of a state runs the requested scope (not DOCS).
- `capt_cli.py` — `capt verify run --scope X [--force] [--command CMD]` and
  `capt verify status`. Independent of memory runtime; no network I/O.
- `.gitignore` — `.capt_verify/` (local-only verification cache).

## Acceptance criteria — demonstrated
| Criterion | Demonstrated by |
|-----------|-----------------|
| Unchanged state reuses verification | `test_unchanged_state_reuses_verification` (2nd call CURRENT, 0 reruns) |
| Changed HEAD invalidates | `test_changed_head_invalidates` (head_changed → FULL rerun) |
| Dirty tree invalidates only affected scopes | `test_dirty_tree_invalidates_only_affected_scope` (math CURRENT, docs REQUIRED) |
| Documentation-only avoids full-suite | `test_documentation_only_avoids_full_suite` (scope=DOCS, no suite) |
| Targeted verification selection | `test_targeted_verification_selection` (narrow scopes; SUITE for multi; FULL for unknown) |
| Evidence reuse | `test_evidence_reuse` (reused_evidence location matches) |
| No verification loops | `test_no_verification_loop` (5 identical calls → 1 run) |

## Bugs found & fixed during implementation
1. `working_tree_status` was in the equivalence identity → untracked `.capt_verify/`
   artifacts broke reuse. Fixed by excluding it from `identity_tuple`.
2. First-ever verification fell through to `decide_scope([], set())` → DOCS (wrong
   scope). Fixed: when `latest is None`, run the requested scope.
3. `mark_superseded` marked the global latest record, wrongly superseding a
   different-scope record. Fixed: supersede only the prior same-scope record.
4. DOCS run-path forced `VERIFICATION_CURRENT` even when a doc change was detected.
   Fixed: run-path always reports REQUIRED (reuse path is the only CURRENT).
5. CLI `repo` path was `dirname(dirname(__file__))` → resolved to parent of repo
   (HEAD `unknown`). Fixed to `dirname(__file__)` (capt_cli.py is at repo root).

## Test commands and exact results
```
python3 -m pytest tests/test_verification_vsi.py -q
# 8 passed
python3 -m pytest -q
# 594 passed (full suite; +8 VSI tests over prior 586)
python3 capt_cli.py verify run --scope engine_math   # REQUIRED, runs
python3 capt_cli.py verify run --scope engine_math   # CURRENT, reuses (no rerun)
python3 capt_cli.py verify status                    # shows head d355c743b3d8
```

## Limitations
- VSI equivalence for FULL scope hashes all tracked files; very large repos may
  incur hashing cost (acceptable; scoped verification is the common path).
- The default runner executes pytest via subprocess; for doc-only scopes it is a
  no-op (no suite invocation), satisfying "documentation-only avoids full-suite."
- Verification records are local (`.capt_verify/`, git-ignored); not shared across
  machines. Cross-machine reuse would require a shared store (future work).
- This is a reusable CAPT capability, not a repository-specific patch; it can be
  lifted into CAPT_core for all long-running missions.

## Files changed
- `capt_solo/verification/__init__.py` (new package)
- `capt_solo/verification/identity.py` (new)
- `capt_solo/verification/scope.py` (new)
- `capt_solo/verification/record.py` (new)
- `capt_solo/verification/store.py` (new)
- `capt_solo/verification/engine.py` (new)
- `capt_cli.py` (verify command group)
- `.gitignore` (.capt_verify/)
- `docs/VSI_MODEL.md` (model doc)
- `docs/CHANGELOG.md` (entry)
- `tests/test_verification_vsi.py` (new, 8 tests)
