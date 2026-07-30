# IMPLEMENTATION_PRECHECK — environment, branch, baseline, rollback, readiness

Generated: 2026-07-30. Per mission Phase 10. NO runtime behavior changed.

## 1. Working tree
- Path: `/Users/knowurknot/capt-solo`
- Branch: `integration/capt-v05-release-corrected` @ `716ecc933eb45b31a0ec461c72ce4ced3da3b2b7`
- `git status --short` (excluding untracked `.capt_state/`): CLEAN
- Python: 3.12.13 (repo-local `.venv`)
- Note: `capt workspace status` / agent startup regenerates CHECKPOINT.md
  (defect B2) — must be suppressed during validation; tracked file reverted
  after each run in this pass.

## 2. Remotes
- origin → github.com/knowurknottty/CAPT_core (PUBLIC; default main `55e149b`)
- preservation → github.com/knowurknottty/capt-core-v05-hardening-backup (PRIVATE)
- Integration branch `716ecc9` is on `preservation` AND local; NOT on `origin`.

## 3. Correct base SHA (proven)
- Source commit: `3888f08e3dc054c67f79114f60c55c4aab5da687` (ancestor of HEAD) ✅
- Metadata tip: `be4b0da8c28f44ce6f89a439dc34710b6fe9ccb7` (ancestor of HEAD) ✅
- Option A lineage: 3888f08 → … → be4b0da → … → 716ecc9 ✅
- 715-test result: reproduced today (`715 passed`) ✅
- Artifact build: `capt_solo-0.5.0-py3-none-any.whl` (sha256 78e49f1b…3396),
  sdist (sha256 4f7d5b85…80e8) ✅
- Clean-install: fresh venv import + `capt --help` ✅
- Release validator: `capt release validate --final` 12/12 exit 0 ✅

## 4. Preserved rollback points
- `716ecc9` on local + preservation remote (integration tip).
- `3888f08` (source) + `be4b0da` (metadata) preserved as ancestors.
- Public `main` `55e149b` untouched; recoverable independently.
- Backup repo: forensic copy, zero unique commits (verified).

## 5. Proposed implementation branch
- `integration/capt-v05-treasure-convergence`
- Create ONLY after: (a) owner approves scope reconciliation (OD-1/OD-2),
  (b) owner approves merge direction OD-4, (c) base SHA `716ecc9` re-confirmed.
- Fork point: `716ecc9`.

## 6. Test commands (enumerated)
```
python -m pytest tests/ -q                 # full suite (715)
python -m build                            # wheel + sdist
capt release validate --final              # 12-check gate
capt workspace validate                    # workspace gate
capt --json doctor                         # lifecycle gate
python -m compileall -q capt_solo          # syntax gate
# security campaign (Package C):
bandit -r capt_solo -x '*/tests/*'
semgrep --config auto capt_solo
gitleaks detect --source . --config .gitleaks.toml
pip-audit -r requirements.txt
```

## 7. Release gates (doc 07)
- Pre-freeze: all code committed, findings disposed, no unexplained worktree
  change, `.capt_state/` untracked, architecture/workspace/release validators
  pass, focused security regressions pass, docs accurate.
- Freeze: capture SHA + `git status`, verify remote contains SHA, record
  tool versions, NO tracked-file edits during verification.
- Machine-enforced failures: version disagree, stale SHA, missing package,
  import drift, stale hashes, unsafe files shipped, network on import, test/
  validator fail, missing security report, dirty tree.

## 8. Readiness state
- Repository ready for Package A (done) and Package B (hygiene).
- Ready for Package C pending OD-4.
- NOT ready for D/E (owner decision OD-1/OD-2).
- NOT ready for freeze: doc 07 evidence files absent, security campaign not
  run at SHA, PUBLIC_CLAIM_LEDGER ❌ items open.
- Overall: NOT READY — BLOCKERS REMAIN (per doc 00).

## 9. Stop conditions triggered?
- Spaces would change stable public API? → would EXTEND, not change; if design
  drifts to signature change, STOP (Package D deferred, so moot now).
- Runtime adapters make Hermes mandatory? → forbidden by design; STOP if seen.
- Treasure Chest vs public manifest incompatible v0.5 scope? → RESOLVED by
  V0_5_SCOPE_RECONCILIATION split (v0.5.0 vs v0.5.1); needs owner ratification.
- Backup change modifies release identity? → backup has zero unique commits; N/A.
- Migration orphans existing data? → only if Package D proceeds; deferred.
- Correct implementation base cannot be proven? → base PROVEN (§3). N/A.
