# BACKUP_RECOVERY_PLAN — capt-core-v05-hardening-backup

Generated: 2026-07-30. Method: read-only comparison. NO commits made.

## 1. Headline finding (changes the prior plan)

The backup repo contains **ZERO unique commits**. For every backup branch:
`git rev-list --count HEAD..<branch> = 0` (HEAD = `716ecc9`, the local
integration branch, which is also the backup `integration/capt-v05-release-corrected`
tip). The backup's default `a04b6fc` and `cve-v0.2` `51eda9a` are both
ANCESTORS of HEAD. Therefore the backup is a pure forensic copy of already-
present history. There is nothing to cherry-pick from it that is not already in
the integration candidate.

Consequence: the earlier "Batch 1 recovery" plan (BATCH1_CHERRYPICK_IMPACT.md)
is OBSOLETE in two ways:
(a) it targeted the integration baseline, but the missing content (ATE, gitleaks,
    release-security CI, whitepaper) is now IN PUBLIC MAIN, not in the backup;
(b) the backup has no unique content to supply.

## 2. What is actually missing from the integration candidate

Derived from `comm -13 <integration tree> <main tree>` (run today):

| File | Source on main | Classification | Recovery action |
|---|---|---|---|
| `capt_solo/components/anti_token_extraction.py` (386 lines) | main only | Security feature | Bring into integration (Package C) |
| `capt_solo/components/anti_token_extraction.mcp.json` | main only | Security feature config | Bring in |
| `capt_solo/components/__init__.py` | main only | Package init (ATE export) | Bring in / reconcile |
| `.gitleaks.toml` | main only | Secret scanning | Bring in (Package C) |
| `.github/workflows/release-security.yml` | main only | Security CI | Bring in (Package C) |
| `tests/test_v04_anti_token_extraction.py` (575 lines) | main only | Security tests | Bring in (Package C) |
| `docs/ANTI_TOKEN_EXTRACTION.md` | main only | Docs | Bring in (Package F) |
| `docs/ARCHITECTURE_REVIEW_ATE_ADAPTER.md` | main only | Docs | Bring in (Package F) |
| `docs/WHITEPAPER.md` (561 lines) | main only | Positioning | Bring in (Package F, then refresh) |
| `docs/DESIGN.md` | main only | Docs | Review; likely superseded by integration docs |

## 3. Per-area reconciliation (doc 15 Workstream C + prior Batch 1)

- **ATE implementation** (doc 15 C, TC-SECURITY-003): present on main, absent
  from integration. Recover via merge from main (additive new files → LOW
  conflict). NOT from backup.
- **MCP configuration**: `anti_token_extraction.mcp.json` on main; no MCP
  config on integration. Bring in.
- **gitleaks / release-security CI**: on main only. Bring in.
- **provenance-gate tests**: `test_v04_anti_token_extraction.py` + the
  `a479a68` "replace credential extraction assertions with provenance gates"
  change are on main. Bring in.
- **secret-hygiene changes** (`e399d65` secret-hygiene parts: verify_runtime.py,
  CHANGELOG.md, test_v02_*): on main; verify_runtime.py already exists on
  integration — reconcile as a MODIFY, not add.
- **CTP fixes** (`9270986`, `d091c33`, `5e13cdb`): ALREADY PRESENT in
  integration (confirmed by BATCH1_CHERRYPICK_IMPACT.md). DROP.
- **packaging changes** (`5e13cdb`, `0d84407`, `0e72533`, `cdc11ca`): the
  packaging repairs (18 packages, MANIFEST.in, console script) are ALREADY in
  integration (wheel built + clean-installed today). DROP — do not re-apply.
- **release-validator changes**: `ef2d8f3` "add mandatory release validation
  matrix" is on main; integration ALREADY has `release_validation.py` +
  `capt release validate` (more advanced: Option A identity). DROP main's
  version; keep integration's.
- **Option A metadata history**: integration HEAD already carries it
  (`3888f08`→`be4b0da`→`716ecc9`). No recovery needed.

## 4. Exact recovery patch plan (do NOT apply yet)

Package C (see IMPLEMENTATION_WORK_PACKAGES.md) will, after owner approves
merge direction OD-4:

1. From `origin/main`, merge (or cherry-pick, additive) the 10 main-only files
   above into the integration branch.
2. Resolve the single MODIFY conflict: `verify_runtime.py` (secret-hygiene
   string substitutions) — apply main's provenance-gate substitutions on top
   of integration's version.
3. Drop all CTP/packaging/release-validator commits (already present).
4. After merge: rerun full suite (must stay 715+), build, clean-install,
   `capt release validate --final`.
5. Add `docs/release/BACKUP_RECOVERY_APPLIED.md` recording exact SHAs and the
   "zero unique backup commits" finding.

## 5. Reject list (explicitly NOT recovered)

- Any backup branch tip (all are ancestors of HEAD; no unique content).
- `9270986`/`d091c33`/`5e13cdb` (CTP) — present.
- `5e13cdb`/`0d84407`/`0e72533`/`cdc11ca` (packaging) — present, would conflict.
- `ef2d8f3` (release-validation matrix) — integration's validator supersedes.
- `973b4ab` (merge commit) — not cherry-pickable; content covered by the 10
  additive files.

## 6. Rollback

Every recovery is performed on branch `integration/capt-v05-treasure-convergence`
forked from `716ecc9` (preserved on backup remote + local). If anything breaks,
`git reset --hard 716ecc9` restores the verified baseline. Public `main` is
untouched until owner approves the final merge direction.
