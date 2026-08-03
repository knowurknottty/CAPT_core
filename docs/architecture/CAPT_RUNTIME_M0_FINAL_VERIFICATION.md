# CAPT Runtime M0 — Final Composed-Stack Verification

Date: 2026-08-03T04:51:57Z
Composed stack branch: docs/capt-runtime-m0-freeze (HEAD f76b1cb)
Contains: M0-A (6665a6a) + M0-B (0d851c4) + freeze docs (f76b1cb..)
Worktree: /Users/knowurknot/capt-m0a
Env: macOS, Python Python 3.9.6, pytest pytest 8.4.2, ruff ruff 0.15.12, node v22.22.2

## [1] schema generation
generate: OK
## [2] generated-binding drift
DRIFT CHECK: OK (11 generated files match the schema source)
## [3] TypeScript build/type-check
tsc: OK
## [4] targeted M0-A tests
...............................................                          [100%]
47 passed, 61 deselected in 0.40s
## [5] targeted M0-B tests
...................................................                      [100%]
51 passed in 0.12s
## [6] all capt_runtime tests
....................................                                     [100%]
108 passed in 0.48s
## [7] full repository suite
.........                                                                [100%]
469 passed, 44 skipped in 5.09s
## [8] replay/checkpoint tests
..........                                                               [100%]
10 passed, 98 deselected in 0.19s
## [9] capability lifecycle tests
.......................                                                  [100%]
23 passed, 85 deselected in 0.08s
## [10] authority-boundary tests
..........                                                               [100%]
10 passed, 98 deselected in 0.07s
## [11] unauthorized-write/read-only tests
.....                                                                    [100%]
5 passed, 103 deselected in 0.08s
## [12] git diff --check
diff-check: clean
## [13] secret scan (capt_runtime + docs)
docs/ANTI_TOKEN_EXTRACTION.md:13:| Sensitive-input refusal enabled | `is_sensitive_input()` refuses credential *assignments* (password=, api_key=, bearer, private key, recovery code, seed phrase, env secret). Bare tokens (AKIA…, ghp_…) are extraction targets, NOT refused |
## [14] no M0-C implementation
## [15] no RuntimeAggregate implementation
## [16] no RuntimeManifest/RuntimeIdentity implementation
## [17] no external OpenHarness invocation
