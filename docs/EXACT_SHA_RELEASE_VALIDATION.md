# EXACT_SHA_RELEASE_VALIDATION — CAPT Core v0.5

Candidate SHA: `c4b954cc2d3168c3bc5345fab0c0e5d0eaa9ebea`
Branch: `integration/capt-v05-release-corrected`
Generated: 2026-07-30 (post OD-4 convergence)

## Exact-SHA gate status (per doc 07)

| Gate | Status | Evidence |
|---|---|---|
| source commit reproducible | PASS | HEAD = c4b954c, ancestor of verified lineage 716ecc9 |
| metadata branch tip | PASS | UNFROZEN (pre-freeze; freeze writes SHA) |
| 715 tests | PASS | rerun today |
| artifact build | PASS | wheel + sdist |
| wheel clean install | PASS | fresh venv |
| sdist clean install | PASS | separate venv, no-network import |
| no-network-on-import | PASS | socket-deny test |
| core imports without Hermes | PASS | zero hermes imports |
| release validator | PASS (non-final) | candidate_sha=UNFROZEN |
| gitleaks | PASS | no leaks |
| verify_runtime | PASS | 52/1/0 |
| ATE security invariants | PASS | mcp.json network_enabled=false, no creds in args |

## Machine-enforced failure conditions (doc 07 §149) — evaluated
- versions disagree: NO (0.5.0 everywhere)
- current docs identify another SHA: N/A (pre-freeze UNFROZEN by design)
- advertised package missing: NO (components added to REQUIRED_PACKAGES)
- installed imports differ: NO
- artifact hashes stale: NO (recorded in release_evidence/*.json)
- unsafe/private files shipped: NO (gitleaks clean)
- network on core import: NO
- tests/validators fail: NO
- security report absent: PENDING (Phase 6/7 — generate RELEASE_SECURITY_REPORT)
- blocking finding: NONE at code level; freeze pending owner authorization

## Freeze procedure (step 6, not yet executed)
1. Write `candidate_sha: c4b954c` into PUBLIC_API_MANIFEST_V0.5.json.
2. `capt release validate --final` must pass (requires the written SHA).
3. Generate docs/release/RELEASE_VERIFICATION_V0.5.md + artifact manifests.
4. Tag + publish ONLY on owner authorization.

## Current decision
NOT READY — BLOCKERS REMAIN only at the process level (security report doc +
owner freeze authorization). All technical gates PASS.
