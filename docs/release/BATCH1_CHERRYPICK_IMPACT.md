# BATCH 1 CHERRY-PICK IMPACT REPORT — CAPT Core v0.5

Generated: 2026-07-30
Baseline: `integration/capt-v05-release-corrected` @ `be4b0da` (Python 3.12.13)
Method: read-only `git show` / `git diff-tree` per candidate commit. No commits made.
Purpose: commit-level impact before owner approves Batch 1.

## Headline finding (minimality check)

The originally proposed 7 commits included 3 CTP commits
(`9270986`, `d091c33`, `5e13cdb`) that are **ALREADY PRESENT in the baseline**.
Verification:
- Baseline `capt_solo/ctp/journal.py` already defines `class CTPRuntime`,
  `class Receipt`, the `journal_dir` constructor contract, and the
  `raise ValueError("provide journal_dir or journal_path, not both")` guard.
- Baseline `capt_solo/ctp/__init__.py` already exports `CTPRuntime, Receipt`.

Therefore those 3 commits MUST be dropped from Batch 1 — cherry-picking them
would be redundant and would conflict with the baseline's (newer) CTP journal.
This confirms the series is minimal: only the ATE component + secret-scanning CI
+ secret-hygiene test fixes are genuinely absent.

## Minimal cherry-pick series (5 commits, conflict-ordered)

| # | Commit | Source branch | Files | Overlap w/ baseline | Conflict risk |
|---|--------|---------------|-------|---------------------|---------------|
| 1 | `e399d65` (additive parts) | hardening/post-merge-release-gates-clean | ATE component + gitleaks + CI + docs | ATE/gitleaks/CI ABSENT → additive | LOW (new files) |
| 2 | `a479a68` | integration/anti-token-extraction-v0.2 | tests/test_v04_anti_token_extraction.py | file ABSENT until #1 lands | LOW (depends on #1) |
| 3 | `ef2d8f3` | integration/anti-token-extraction-v0.2 | .github/workflows/release-security.yml | ABSENT (same file as #1's CI) | MEDIUM (same-file as #1) |
| 4 | `e399d65` (secret-hygiene parts) | hardening/post-merge-release-gates-clean | verify_runtime.py, CHANGELOG.md, test_v02_* | PRESENT → modifies | MEDIUM (string subs) |
| 5 | `973b4ab` | (MERGE — DO NOT CHERRY-PICK) | — | — | N/A |

`973b4ab` is a **merge commit** (parents `abeff5c` + `9270986`). It is NOT
cherry-pickable as a unit; its effective content is already covered by #1–#4.
Excluded.

## Per-commit detail

### Commit 1 — `e399d65` (additive portion)
Subject: hardening: remove _ate_stdio_server adapter, use real upstream MCP
Files ADDED (safe, absent in baseline):
- `capt_solo/components/anti_token_extraction.py` (386-line ATE component)
- `capt_solo/components/anti_token_extraction.mcp.json`
- `.gitleaks.toml` (secret scanning config)
- `.github/workflows/release-security.yml` (14 lines, initial)
- `docs/ANTI_TOKEN_EXTRACTION.md`
- `docs/ARCHITECTURE_REVIEW_ATE_ADAPTER.md`
- `tests/test_v04_anti_token_extraction.py` (532-line test, NEW)
Files REMOVED: `capt_solo/components/_ate_stdio_server.py` (112 lines) — this file
does NOT exist in baseline, so the deletion is a no-op here (safe).
Subsystem: Security (ATE) + CI.
Overlap: 0/7 added files exist in baseline → no conflict on add.
Public API: NONE (new internal component + CI config).
Migration: NONE.
Tests: adds `test_v04_anti_token_extraction.py`.
Omit? NO — this is the core ATE capability, the point of Batch 1.

### Commit 2 — `a479a68`
Subject: test(security): replace credential extraction assertions with provenance gates
Files: `tests/test_v04_anti_token_extraction.py` (110 ins / 157 del).
Overlap: file is created by Commit 1 → must apply AFTER #1.
Conflict risk: LOW if ordered after #1; the commit rewrites the test file's
assertions to provenance gates (strengthens verification story).
Public API: NONE. Migration: NONE. Tests: modifies the ATE test.
Omit? Optional — improves test quality. Recommend INCLUDE (ordered after #1).

### Commit 3 — `ef2d8f3`
Subject: ci(security): add mandatory release validation matrix
Files: `.github/workflows/release-security.yml` (75 lines, NEW content).
Overlap: same file as Commit 1's 14-line initial version.
Conflict risk: MEDIUM — both #1 and #3 touch `release-security.yml`. Resolve by
either (a) squashing #1's CI hunk + #3 into one file, or (b) applying #3 after #1
and letting git merge the non-overlapping additions (75 new lines vs 14 initial —
likely clean if #3's content is appended/extended). Recommend applying #3 after #1
and verifying the YAML parses.
Public API: NONE. Migration: NONE. Tests: CI only.
Omit? NO — mandatory release validation matrix is valuable CI gate.

### Commit 4 — `e399d65` (secret-hygiene portion)
Subject: (same commit, different hunks) secret-string hygiene in baseline-present files
Files MODIFIED (present in baseline):
- `verify_runtime.py` (+3/-3): replaces hardcoded `password=supersecret123` with
  dynamic `password=` + `"x"*12` in a secret_screen test call.
- `docs/CHANGELOG.md` (+18/-11): describes ATE adapter switch (local child → real
  upstream MCP).
- `tests/test_v02_csg.py` (+1/-1), `tests/test_v02_models.py` (+4/-4),
  `tests/test_v03_integration.py` (+1/-1): same dynamic-secret substitution.
Overlap: ALL 5 files exist in baseline → these are modifications, not adds.
Conflict risk: MEDIUM — string-level substitutions; baseline may have diverged
slightly. If a hunk fails to apply, the change is trivial to re-apply manually
(find `supersecret123` / `abcdefghijklmnopqrstuvwxyz123456` and replace with
dynamic form).
Public API: NONE. Migration: NONE. Tests: hardens secret hygiene in existing tests.
Omit? Optional — pure hygiene. Recommend INCLUDE but as a separate, easily-revertible
commit; if it conflicts, the ATE functionality (#1–#3) does not depend on it.

## Release-semantic change check (owner requirement)

Confirmed: NONE of the Batch 1 commits touch release semantics.
- `capt_solo/release_validation.py`: NOT modified by any candidate commit.
- `docs/release/PUBLIC_API_MANIFEST_V0.5.json`: NOT modified.
- `candidate_sha`, `candidate.sha_match`, `candidate.clean_tree`, Option A logic:
  untouched.
- The `capt release validate --final` gate behavior is unchanged by Batch 1.

The baseline's validator (frozen, passing) remains the authority. Batch 1 is
purely additive security hardening + CI + test hygiene.

## Public API changes

NONE. The ATE component is an internal `capt_solo.components` module (not in the
stable/experimental package list of the public manifest). No entry-point, CLI, or
schema changes. `pyproject.toml` is NOT in the minimal series (it was touched by
`973b4ab` merge only for CTP packaging, already in baseline).

## Migration implications

NONE. No schema, config, or data-format changes. The ATE component reads/writes
its own state; no migration of existing artifacts.

## Can any commit be safely omitted?

- `9270986`, `d091c33`, `5e13cdb` (CTP): OMIT — already in baseline. Including them
  would cause conflicts, not value.
- `973b4ab` (merge): OMIT — not cherry-pickable; content already covered.
- Commit 2 (`a479a68`): OMITTABLE — test-quality improvement, not functional.
- Commit 4 (secret-hygiene): OMITTABLE — hygiene only, easily separated.
- Commits 1 & 3 (ATE component + release-security CI): DO NOT OMIT — these are the
  substance of Batch 1.

## Recommended minimal order

1. `e399d65` additive parts (ATE component, gitleaks, CI init, docs, ATE test)
2. `a479a68` (provenance-gate test rewrite — needs #1's test file)
3. `ef2d8f3` (release validation matrix CI — same file as #1, apply after)
4. `e399d65` secret-hygiene parts (verify_runtime.py, CHANGELOG, test_v02/03)
   — separate commit, revertible.

Total new files: 7 (ATE component + mcp.json + gitleaks + CI + 2 docs + ATE test)
Total modified baseline files: 5 (secret-hygiene only)
Total commits: 4 (down from originally proposed 7; 3 dropped as redundant)

## Verification after apply

- `pytest tests/test_v04_anti_token_extraction.py` (new)
- `pytest tests/` (full, expect 715 + new ATE tests = green)
- `capt doctor` (security surface)
- `capt release validate --final` (must remain ok: True — unchanged semantics)
- YAML lint `.github/workflows/release-security.yml`
