# RELEASE_INTEGRATION_PLAN — CAPT Core v0.5

Generated: 2026-07-30
Baseline: `integration/capt-v05-release-corrected` @ `be4b0da`
Policy: NO automatic merges. Owner approves each batch. Never rewrite history.
Never delete branches — archive only.

## Ordered merge plan

### Batch 0 — Preconditions (already met)
- [x] Option A validator frozen and passing.
- [x] Source commit `3888f08` immutable, `candidate_sha` frozen.
- [x] Full suite green (715 passed) on baseline.
- [x] Branch census + architecture inventory complete (this document set).

### Batch 1 — Anti-Token-Extraction (ATE) security hardening [CHERRY-PICK]
Source branch: `hardening/post-merge-release-gates-clean` (e399d65, preferred)
Secondary: `integration/anti-token-extraction-v0.2` (provenance-gate tests)

Commits to cherry-pick (in order):
1. `973b4ab` feat(v0.4.1): integrate hardened Anti-Token-Extraction
2. `9270986` fix(ctp): preserve v0.4 journal_dir constructor contract
3. `d091c33` fix(release): restore omitted CTP journal runtime
4. `5e13cdb` fix(packaging): make CTP an explicit distributable package
5. `e399d65` hardening: remove _ate_stdio_server adapter, use real upstream MCP
6. `.gitleaks.toml` + `.github/workflows/release-security.yml` (secret scanning + CI)
7. Provenance-gate test patterns from `a479a68`, `ef2d8f3` (if not in clean branch)

Expected conflicts: LOW. `capt_solo/components/` is new to baseline; CTP commits
must apply on top of baseline's existing `capt_solo/ctp/` — verify journal.py
compatibility. CI files are additive.

Testing order after Batch 1:
1. `pytest tests/test_v04_anti_token_extraction.py` (brings from branch)
2. `pytest tests/test_ctp.py`
3. `capt doctor` (security surface)
4. `capt release validate --final` (gate must stay green)

Rollback: `git revert` the cherry-pick commits (no history rewrite). Or reset the
integration branch to `be4b0da` (preserved on remote).

### Batch 2 — Documentation gaps [LOW RISK]
- Add `docs/khsb.md` (KHSB bus, declared stable, undocumented).
- Add `docs/foundry.md` (Proof Engine registry/columns).
- Add `docs/ctp.md` (journal runtime contract).
- Mark `engines`, `ontology` as internal/experimental in docs OR add tests.

Expected conflicts: NONE (doc-only).

### Batch 3 — Engines / Ontology test coverage [MEDIUM RISK]
- Add `tests/test_engines.py`, `tests/test_ontology.py` (smoke + contract).
- If tests reveal instability, move packages to experimental in manifest.

Expected conflicts: NONE (test-only). Risk: may surface latent bugs → owner review.

## Conflict expectations summary
| Target | Conflict risk | Notes |
|--------|---------------|-------|
| ATE component | LOW | new dir `capt_solo/components/` |
| CTP journal | MEDIUM | baseline already has ctp/journal.py; verify merge |
| gitleaks CI | LOW | additive |
| docs | NONE | additive |
| engines/ontology tests | NONE | additive |

## Testing order (global)
1. Unit: `pytest tests/test_release_identity_option_a.py tests/test_release_semantics.py`
2. Subsystem: `pytest tests/test_ctp.py tests/test_khsb.py tests/test_evidence_*.py`
3. Full: `pytest tests/`
4. Gate: `capt release validate --final`
5. Install: `python -m build` + clean venv install + `capt doctor`

## Rollback strategy
- Every batch is a single commit or small commit series on the integration branch.
- Rollback = `git revert <commit>` (preserves history, satisfies no-rewrite rule).
- The source baseline `3888f08` and corrected branch `be4b0da` are both preserved
  on the `preservation` remote — a full reset is always possible.
- Never `git reset --hard` across shared history; use revert.

## Owner approval gates
- Batch 1 requires explicit owner sign-off (security subsystem, CTP coupling).
- Batches 2–3 are low-risk; owner may pre-approve or review per-commit.
- No merge to `main`, no tag, no publish until all batches green and owner declares.
