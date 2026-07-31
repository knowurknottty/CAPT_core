# KNOWN_BLOCKER_CORRECTION_RECORD — Phase A

Generated: 2026-07-30. Governing procedure: captstreasurechest
docs/16_V0_5_POST_AUDIT_RELEASE_WORKFLOW.md (Phase A).

## Pre-correction state
- Branch: `integration/capt-v05-release-corrected`
- Pre-correction SHA: `7b9bcf422c69d3afbbe600d64239c6dd8c3cea71`
- Working tree: had untracked Pass 3/4 audit deliverables (not part of source)
- Validator (pre): `public_api.package_inventory` FAIL (10 pass / 1 fail)
- Reports `docs/security/RELEASE_SECURITY_REPORT_V0.5.md` and
  `docs/release/RELEASE_VERIFICATION_V0.5.md`: ABSENT

## Reproduction of findings (independent, not trusted from reports)
- F1: `capt release validate` → `public_api.package_inventory: fail`. Declared
  packages (manifest) = 18 (no `capt_solo.components`); source tree = 19
  (includes `capt_solo/components`). Reproduced.
- F5: README links to two report paths; both `MISSING` on disk. Reproduced.

## Corrections applied (minimum, scoped to F1 + F5 only)
1. `docs/release/PUBLIC_API_MANIFEST_V0.5.json`
   - Added `"capt_solo.components"` to `packages.stable`.
   - Reason: F1 — manifest declared inventory omitted the recovered ATE
     component, causing `public_api.package_inventory` validator failure.
   - Evidence: source has `capt_solo/components/__init__.py`; wheel + sdist +
     installed wheel all contain `capt_solo/components`.

2. `docs/security/RELEASE_SECURITY_REPORT_V0.5.md` (NEW)
   - Reason: F5 — README references this path; it was absent.
   - Content derived ONLY from regenerated evidence: gitleaks (no leaks),
     verify_runtime (52/1/0), doctor injection (5 pass), security suite (35
     pass), no-network import, zero-Hermes import, ATE `verify_pinned_commit`.

3. `docs/release/RELEASE_VERIFICATION_V0.5.md` (NEW)
   - Reason: F5 — README references this path; it was absent.
   - Content: regenerated test counts (711 pass / 4 freeze-gate fail / 44
     skip), validator pre/post state, artifact hashes, reproducibility note.

4. `docs/EXACT_SHA_RELEASE_VALIDATION.md` (CORRECTED)
   - Reason: prior doc falsely stated "715 tests PASS" and "release validator
     PASS". Independent re-run showed validator FAILED and true count is
     711/4/44. Corrected per owner authorization.

5. `docs/BASELINE_REVALIDATION.md` (CORRECTED)
   - Reason: same false "715 passed" / validator-PASS claim. Corrected.

## Post-correction state
- Corrected candidate SHA: `be2863508e47c3cb9ea4b4320ebab29bdcf64d94`
- Validator (post): 10 pass / 0 fail (`public_api.package_inventory` now PASS)
- Both required reports exist at advertised paths.
- README links to both reports now resolve.

## Files changed (exact)
- M docs/release/PUBLIC_API_MANIFEST_V0.5.json
- A docs/security/RELEASE_SECURITY_REPORT_V0.5.md
- A docs/release/RELEASE_VERIFICATION_V0.5.md
- M docs/EXACT_SHA_RELEASE_VALIDATION.md
- M docs/BASELINE_REVALIDATION.md

## Confirmation: no unrelated files changed
The commit `be28635` staged ONLY the five files above. The untracked Pass 3/4
audit deliverables (`docs/convergence/RECURSION_PASS_*.md`,
`release_evidence/recursion_pass_3_findings.json`) were deliberately excluded
from this correction commit. No source code, no API, no architecture, no scope
change. Diff summary: +components to manifest; +2 new report files; corrected 2
docs' false PASS claims.

## Residual note (not a Phase A blocker, recorded for Phase B)
The 4 failing tests are Option A freeze-gate regression tests that require a
clean frozen tree (`candidate_sha` set + untracked files committed). They fail
in the current UNFROZEN/dirty state by design. They are not implementation
defects and are outside Phase A's two-blocker scope.
