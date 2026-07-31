# CROSS_PLATFORM_INSTALLATION_MATRIX — Phase D

Candidate SHA: `be2863508e47c3cb9ea4b4320ebab29bdcf64d94`
Wheel: 8889ead6664cb90bd479fbaac2aac3db214a82a5ee049950ee3ed99b4c114a53
Date: 2026-07-30. Governing: captstreasurechest docs/16_V0_5_POST_AUDIT_RELEASE_WORKFLOW.md (Phase D).

## Declared support
- `requires-python = ">=3.8"` (pyproject)
- Classifiers: "Programming Language :: Python :: 3" (generic, no OS pin)
- No explicit OS claim in README or metadata.

## Test method
For each environment: fresh venv OUTSIDE the repository; wheel install; import +
version; CLI help; doctor; no-network import; sdist install (separate venv);
uninstall; reinstall; ATE import; package-resource access. `capt release validate`
is run but EXCLUDED from portability claims because the README states it
requires a source checkout (repository-only command). See "release validate"
note below.

## Matrix results

| Environment | Py | wheel | import | cli | doctor | no-net | sdist | uninstall | reinstall | ate | resource | Result |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| macOS arm64 (Apple Silicon) | 3.10.20 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| macOS arm64 (Apple Silicon) | 3.12.13 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| macOS arm64 (Apple Silicon) | 3.14.6 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Linux Ubuntu 22.04 (glibc) | 3.10 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Linux Ubuntu 24.04 (glibc) | 3.12.3 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |

All 11 portable checks PASS on every tested environment.

## `capt release validate` note (NOT a portability claim)
When run from an installed environment WITHOUT the source checkout, `capt
release validate` fails with "checks: 1, passed: 0, failed: 1" because it reads
`docs/release/PUBLIC_API_MANIFEST_V0.5.json` from the current working directory
(repository-only file). The README explicitly states: "Repository-only commands
such as architecture and workspace validation require a source checkout
containing the governed files they inspect." Therefore `release validate` is
classified as requiring a source checkout, not as an installed-environment
portability check. It PASSES when run inside the repo (verified in Phase B).

## Windows 11 — ENVIRONMENT_LIMITATION (owner-accepted residual)
Docker Desktop on macOS cannot run Windows containers, so a native Windows 11
installation was not executed in this audit. The package is pure-Python
(py3-none-any wheel, only `pyyaml` dependency, no C extensions, no OS-specific
code paths in core). The risk of Windows failure is low but UNTESTED. Per
workflow §7.8, this is recorded as an ENVIRONMENT_LIMITATION / owner-accepted
residual: Windows 11 is NOT claimed as verified in this release. If the owner
requires Windows support, a Windows 11 CI runner or VM test must be added before
that claim is made.

## Python 3.8 / 3.9 — ENVIRONMENT_LIMITATION (owner-accepted residual)
`requires-python >=3.8` is declared, but local runtimes available were 3.10,
3.12, 3.14 (macOS arm64) and 3.10/3.12 (Linux Docker). Python 3.8 and 3.9 were
not executed. The code uses no 3.10+ syntax that would break 3.8 (verified by
import on 3.10+ and absence of 3.10-only constructs in core modules), but 3.8/
3.9 are UNTESTED in this audit. Recorded as ENVIRONMENT_LIMITATION: the
`>=3.8` claim is not fully verified; either test on 3.8/3.9 or narrow the
claim to `>=3.10`.

## Portability gate decision (workflow §7.8)
- All DECLARED-and-TESTED environments pass (macOS arm64 3.10/3.12/3.14, Linux
  glibc 3.10/3.12).
- Untested environments (Windows 11, Python 3.8/3.9) are explicitly documented
  as residual limitations, NOT claimed as supported in this release.
- No PACKAGE_BLOCKER, INSTALLER_BLOCKER, or PLATFORM_BLOCKER found in tested
  matrix.

## Conclusion
PASS for the tested matrix. Windows 11 and Python 3.8/3.9 are owner-accepted
residual limitations (documented, not claimed). No code change required.
