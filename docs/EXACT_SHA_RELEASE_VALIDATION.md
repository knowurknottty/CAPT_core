# EXACT_SHA_RELEASE_VALIDATION — CAPT Core v0.5

Candidate SHA: `7b9bcf422c69d3afbbe600d64239c6dd8c3cea71`
Branch: `integration/capt-v05-release-corrected`
Generated: 2026-07-30 (post OD-4 convergence; corrected 2026-07-30 in Phase A)

> CORRECTION NOTICE: this document previously (at `c4b954c`) falsely stated
> "715 tests PASS" and "release validator PASS". Independent re-run (Pass 3)
> showed the validator FAILED (`public_api.package_inventory`) and the true
> test count is 711 passed / 4 freeze-gate failures. Corrected below.

## Exact-SHA gate status (per doc 07, regenerated at `7b9bcf4`)

| Gate | Status | Evidence |
|---|---|---|
| source commit reproducible | PASS | HEAD = 7b9bcf4, ancestor of verified lineage 716ecc9 |
| metadata branch tip | PASS | UNFROZEN (pre-freeze; freeze writes SHA) |
| test suite | 711 passed / 4 failed / 44 skipped | 4 failures are Option A freeze-gate tests (expected pre-freeze) |
| artifact build | PASS | wheel + sdist |
| wheel clean install | PASS | fresh venv |
| sdist clean install | PASS | separate venv, no-network import |
| no-network-on-import | PASS | socket-deny test |
| core imports without Hermes | PASS | zero hermes imports |
| release validator (pre-correction) | **FAIL** | `public_api.package_inventory` — manifest omitted `capt_solo.components` |
| release validator (post-correction) | PASS | 10/10 (Phase A added components to manifest) |
| gitleaks | PASS | no leaks |
| verify_runtime | PASS | 52/1/0 |
| ATE security invariants | PASS | mcp.json network_enabled=false, no creds in args |

## Machine-enforced failure conditions (doc 07 §149) — evaluated
- versions disagree: NO (0.5.0 everywhere)
- current docs identify another SHA: N/A (pre-freeze UNFROZEN by design)
- advertised package missing: **YES pre-correction** (components omitted) → FIXED in Phase A
- installed imports differ: NO
- artifact hashes stale: NO (recorded in release_evidence/*.json)
- unsafe/private files shipped: NO (gitleaks clean)
- network on core import: NO
- tests/validators fail: **YES pre-correction** (validator fail + 4 freeze-gate) → validator fixed; freeze-gate expected pre-freeze
- security report absent: RESOLVED in Phase A (RELEASE_SECURITY_REPORT_V0.5.md generated)
- blocking finding: F1 (validator) resolved; freeze pending owner authorization

## Freeze procedure (step 6, not yet executed)
1. Write `candidate_sha: <frozen SHA>` into PUBLIC_API_MANIFEST_V0.5.json.
2. `capt release validate --final` must pass (requires the written SHA + clean tree).
3. Commit audit evidence so the tree is clean (freeze-gate tests require it).
4. Tag + publish ONLY on owner authorization.

## Current decision
NOT READY — blockers F1 (validator) RESOLVED in Phase A; F5 (reports) RESOLVED
in Phase A. Remaining: freeze-gate tests require a clean frozen tree (owner
freeze step), and owner freeze authorization.
