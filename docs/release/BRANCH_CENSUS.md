# BRANCH_CENSUS — CAPT Core v0.5

Generated: 2026-07-30
Baseline for comparison: `integration/capt-v05-release-corrected` @ `be4b0da`
Method: read-only git inspection (rev-list counts, merge-base ancestry, diff
filters). No merges, no history rewrites, no deletions performed.

## Summary table

| Branch | Ahead/Behind vs baseline | Ancestor of baseline? | Disposition |
|--------|--------------------------|----------------------|-------------|
| `main` | 0 / 61 | YES | Archive (v0.4 root) |
| `integration/full-public-architecture` | 0 / 23 | YES | Archive (absorbed: Evidence Engine) |
| `codex/capt-v0.5-p0-release-hardening` | 1 / 2 | NO (parallel looped lineage) | Archive (superseded by corrected branch) |
| `codex/cve-v0.2-operational-continuity` | 0 / 12 | NO (docs only) | Archive (docs absorbed) |
| `preservation/security-fixes-706-pass` | 0 / 2 | YES (== 3888f08) | Preserved (source baseline) |
| `preservation/hy3-sha-loop-20260730-124704` | 1 / 2 | NO | Archive (incident artifact) |
| `hardening/ate-clean-single` | 17 / 61 | NO | **Cherry-Pick** (ATE/CTP security) |
| `hardening/post-merge-release-gates` | 18 / 61 | NO | **Cherry-Pick** (ATE + CI) |
| `hardening/post-merge-release-gates-clean` | 16 / 61 | NO | **Cherry-Pick** (cleanest ATE) |
| `integration/anti-token-extraction-v0.2` | 14 / 61 | NO | **Cherry-Pick** (ATE v0.2) |

## Detailed dispositions

### `main` (abeff5c) — ARCHIVE
- v0.4 release root. Baseline is a descendant (main IS an ancestor of `be4b0da`).
- 61 commits behind baseline; contains none of the v0.5 subsystems (ctp, evidence,
  verification, memory, foundry, knowledge, contextpack, etc. are all absent on main).
- Disposition: **Archive** as the historical v0.4 tag source. No merge needed —
  its content is fully contained in the baseline.

### `integration/full-public-architecture` (77fdcdf) — ARCHIVE
- Evidence Engine + VSI integration branch (v0.4.2 era).
- Confirmed ancestor of baseline (`merge-base --is-ancestor` = YES). All 38 of its
  unique commits (Evidence Engine core, VSI, workspace isolation, proof graph) are
  already in the baseline tree.
- Disposition: **Archive** — work already shipped in baseline. No action.

### `codex/capt-v0.5-p0-release-hardening` (0588e71) — ARCHIVE
- The original v0.5 hardening line that entered the SHA-loop incident.
- NOT an ancestor of the corrected baseline. Its unique commits (security fixes at
  3888f08, looped freeze attempts) are either preserved at `preservation/security-fixes-706-pass`
  or superseded by `integration/capt-v05-release-corrected`.
- Disposition: **Archive** as incident history. The valid security work is preserved
  separately at `preservation/security-fixes-706-pass` (3888f08).

### `codex/cve-v0.2-operational-continuity` (51eda9a) — ARCHIVE
- Documentation branch: "converge CAPT v0.5 platform model", ContextPack v1 docs,
  gated verification status. 49 commits beyond main, 0 files added vs baseline
  (docs already present in baseline tree).
- Disposition: **Archive** — documentation already absorbed into baseline. No merge.

### `preservation/security-fixes-706-pass` (3888f08) — PRESERVED (do not touch)
- The immutable source commit for v0.5. Already the `candidate_sha` target.
- Disposition: leave as-is. This is the foundation.

### `preservation/hy3-sha-loop-20260730-124704` (0588e71) — ARCHIVE
- Safety branch created during the SHA-loop incident recovery.
- Disposition: **Archive** as incident artifact. No merge.

### `hardening/ate-clean-single` (b6a5950) — CHERRY-PICK
- v0.4.1 Anti-Token-Extraction (ATE) hardening + CTP journal runtime restoration.
- 17 commits beyond main, NOT in baseline. Unique files vs baseline:
  - `capt_solo/components/anti_token_extraction.py` (the ATE component — absent in baseline)
  - `capt_solo/components/anti_token_extraction.mcp.json`
  - `.gitleaks.toml` (secret scanning config — absent in baseline)
  - `.github/workflows/release-security.yml` (absent in baseline)
  - `docs/ANTI_TOKEN_EXTRACTION.md`, `docs/ARCHITECTURE_REVIEW_ATE_ADAPTER.md`
  - `tests/test_v04_anti_token_extraction.py`
- Quality: "VALIDATED LOCALLY AND IN CI" per last commit. Removes the `_ate_stdio_server`
  adapter in favor of real upstream MCP (secret-clean).
- Risk: Moderate. ATE is a security subsystem; integrating it into the v0.5 tree
  requires verifying it doesn't conflict with the baseline's `capt_solo/ctp` package.
- Disposition: **Cherry-Pick** the ATE component + gitleaks + release-security CI.
  Recommended commits: `973b4ab` (integrate ATE), `9270986` (CTP journal contract),
  `d091c33` (restore CTP journal runtime), `5e13cdb` (CTP packaging), `e399d65`
  (remove adapter, use upstream MCP), plus gitleaks/CI commits.

### `hardening/post-merge-release-gates` (d81a3d9) — CHERRY-PICK
- Same ATE lineage as `ate-clean-single` plus `docs(test): remove credential-shaped
  substrings` and `test(security): construct secret fixtures dynamically`.
- 18 commits beyond main. Unique files identical to ate-clean-single (8 added).
- Disposition: **Cherry-Pick** — prefer `hardening/post-merge-release-gates-clean`
  (below) as the cleaner source; use this branch only for the secret-fixture test
  improvements if not present in the clean variant.

### `hardening/post-merge-release-gates-clean` (e399d65) — CHERRY-PICK (preferred)
- Cleanest ATE variant: "remove _ate_stdio_server adapter, use real upstream MCP
  (live-validated, secret-clean)". 16 commits beyond main.
- This is the recommended source for the ATE cherry-pick — it has the secret-clean
  adapter removal already applied.
- Disposition: **Cherry-Pick** as the primary ATE integration source.

### `integration/anti-token-extraction-v0.2` (9270986) — CHERRY-PICK
- ATE v0.2: includes `_ate_stdio_server.py` (the adapter the clean branches removed)
  plus CI security matrix and provenance-gate tests. 14 commits beyond main.
- Disposition: **Cherry-Pick** selectively — use for the provenance-gate test
  patterns (`a479a68`, `ef2d8f3`) which strengthen the baseline's verification
  story. Do NOT bring `_ate_stdio_server.py` (superseded by upstream-MCP approach).

## Branches not enumerated
- Detached worktrees from the forensic recovery phase (4 worktrees) are excluded
  from merge consideration; they were preserved read-only and are not part of the
  active branch set. Their content is reachable from the preservation remote.

## Conflicts expected
- ATE cherry-picks will land `capt_solo/components/` which does not exist in baseline
  → low conflict risk for the component itself.
- `capt_solo/ctp/` already exists in baseline; the ATE branches' CTP commits
  (`9270986`, `d091c33`) modify CTP journal runtime — must verify they apply cleanly
  on top of the baseline's CTP, which may have diverged.
- `.github/workflows/` is absent in baseline → gitleaks/release-security CI adds
  without conflict but needs CI runner validation.

## Recommendation
1. Cherry-pick ATE from `hardening/post-merge-release-gates-clean` (primary).
2. Add gitleaks + release-security CI from the same branch.
3. Pull provenance-gate test patterns from `integration/anti-token-extraction-v0.2`.
4. Archive all other branches (no merge). They are either ancestors (absorbed) or
   incident artifacts.
5. Owner approves each cherry-pick batch before application.
