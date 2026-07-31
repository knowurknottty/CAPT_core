# INSTALLER_PORTABILITY_FINDINGS — Phase D

Candidate SHA: `be2863508e47c3cb9ea4b4320ebab29bdcf64d94`

## Findings

### D1 — `capt release validate` requires source checkout [DOCUMENTATION_BOUNDARY, not a defect]
- Evidence: outside repo, `capt release validate` → "checks: 1, passed: 0,
  failed: 1" (cannot locate `docs/release/PUBLIC_API_MANIFEST_V0.5.json`).
  Inside repo, it passes (Phase B).
- Classification: DOCUMENTATION_BOUNDARY. The README already states
  repository-only commands require a source checkout. No code change.
- Public impact: none, if docs remain accurate. README is accurate.
- Action: none required. Excluded from installed-environment portability claim.

### D2 — Windows 11 untested [ENVIRONMENT_LIMITATION]
- Evidence: Docker Desktop on macOS cannot run Windows containers; no Windows
  runner available this session.
- Classification: ENVIRONMENT_LIMITATION (owner-accepted residual).
- Public impact: Windows 11 not verified. Package is pure-python (py3-none-any,
  pyyaml only, no C ext, no OS-specific core paths) → low risk but untested.
- Action: owner may add Windows CI before claiming Windows support, or accept
  as documented residual.

### D3 — Python 3.8 / 3.9 untested [ENVIRONMENT_LIMITATION]
- Evidence: local runtimes 3.10/3.12/3.14 (macOS) + 3.10/3.12 (Linux Docker).
  3.8/3.9 not present.
- Classification: ENVIRONMENT_LIMITATION (owner-accepted residual).
- Public impact: `requires-python >=3.8` claim not fully verified for 3.8/3.9.
- Action: test on 3.8/3.9 or narrow metadata to `>=3.10`.

### D4 — All tested environments PASS [PASS]
- macOS arm64 (3.10/3.12/3.14) + Linux glibc (3.10/3.12): 11/11 portable checks
  pass on each. No INSTALLER_BLOCKER, PACKAGE_BLOCKER, or PLATFORM_BLOCKER.

## Classification summary
- INSTALLER_BLOCKER: none
- PACKAGE_BLOCKER: none
- PLATFORM_BLOCKER: none
- DOCUMENTATION_BOUNDARY: D1 (already documented)
- ENVIRONMENT_LIMITATION: D2 (Windows), D3 (Py3.8/3.9)
- FALSE_POSITIVE: none
- OWNER_ACCEPTED: D2, D3
