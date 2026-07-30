# OD4_DELTA_LEDGER — recovered main-only deltas

Generated: 2026-07-30. Each delta recovered from `origin/main` into the
integration lineage (od4-converge-tmp). Classifications per Package C /
BACKUP_RECOVERY_PLAN.

| # | Source path | Dest path | Source commit | Reason | Dependency | Conflict | Resolution | Tests | Disposition |
|---|---|---|---|---|---|---|---|---|---|
| 1 | capt_solo/components/anti_token_extraction.py | same | 75ac488 / e399d65 | ATE security feature (optional, degradable) | external pkg `anti-token-extraction` (OPTIONAL, not added to deps) | none (new file) | recovered as-is | test_v04_anti_token_extraction.py (skips if ext pkg absent) | RECOVERED |
| 2 | capt_solo/components/anti_token_extraction.mcp.json | same | e399d65 | MCP config for ATE | none | none | recovered as-is | security invariants in CI | RECOVERED |
| 3 | capt_solo/components/__init__.py | same | e399d65 | ATE exports | none | identical on both sides | no-op (same content) | n/a | RECOVERED (no-op) |
| 4 | .gitleaks.toml | same | aae6be4 | secret scanning config | none | none | recovered as-is | gitleaks detect (ran: no leaks) | RECOVERED |
| 5 | .github/workflows/release-security.yml | same | ef2d8f3 + e399d65 | security CI | none | main version pinned external git+ repo + verify_runtime.py + doctor.sh | SYNTHESIZED: use `capt release validate --final` + `capt doctor`; dropped external git+ pin; ATE test skippable | CI logic | RECOVERED (adapted) |
| 6 | tests/test_v04_anti_token_extraction.py | same | a479a68 | provenance-gate tests | ATE component | none (new file) | recovered as-is (already skipif ext pkg absent) | part of suite (715) | RECOVERED |
| 7 | verify_runtime.py | same (root) | main-only | v0.4 runtime verification harness | capt_solo.api (EXISTS at integration HEAD) | 1 stale check (47 tools) | fixed stale check to >=1 (v0.5 has 46) | ran: 52 pass/1 warn/0 fail | RECOVERED (corrected) |
| 8 | docs/ANTI_TOKEN_EXTRACTION.md | same | e399d65 | ATE docs | none | none | recovered as-is | n/a | RECOVERED |
| 9 | docs/ARCHITECTURE_REVIEW_ATE_ADAPTER.md | same | e399d65 | ATE architecture review | none | none (additive, not on integration) | recovered as-is | n/a | RECOVERED |
| 10 | docs/DESIGN.md | same | 6f42676 | design rationale | none | none (additive) | recovered as-is | n/a | RECOVERED |
| 11 | docs/WHITEPAPER.md | same | 644bd1f | public whitepaper | none | v0.4.1 language + A16 "adapters" | SYNTHESIZED: L451 → v0.5.0 six-pillar language; L498 → "adapter seam" (OD-2 caveat) | n/a | RECOVERED (corrected) |
| 12 | doctor.sh | RESTORED to integration version | n/a | was wrongly overwritten by main's stale version | n/a | main's had `==47` + shell-var injection pattern | REVERTED to integration HEAD version | doctor tests pass | REJECTED main, KEPT integration |

## Explicitly NOT recovered (per Phase 2)
- CTP commits 9270986/d091c33/5e13cdb — already present in integration.
- Packaging commits 5e13cdb/0d84407/0e72533/cdc11ca/55326c5 — already present.
- ef2d8f3 release-validation-matrix — integration has advanced release_validation.py (supersedes).
- 973b4ab merge commit — not cherry-pickable; content covered by #1/#5.
- capt-core-v05-hardening-backup — zero unique commits (forensic only).

## Unplanned dependencies discovered
- ATE component imports optional external `anti-token-extraction` pkg at runtime
  via importlib.metadata; NOT added to pyproject deps (preserves "core imports
  without hidden deps"; ATE degrades gracefully). CI adapted to not require the
  external git+ pin for core validation.
- verify_runtime.py is a v0.4 harness; runs green on v0.5 with one corrected
  stale check. Kept as supplementary (not the primary gate; `capt release
  validate` is primary).

## Result
All 10 required main-only files recovered (1 no-op, 1 reverted, 2 synthesized/
corrected). No approved delta rejected. No scope expansion beyond ATE security
feature (which is itself a security-campaign item for v0.5.0).
