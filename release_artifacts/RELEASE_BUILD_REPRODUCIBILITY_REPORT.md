# RELEASE_BUILD_REPRODUCIBILITY_REPORT — Phase C

Candidate SHA: `be2863508e47c3cb9ea4b4320ebab29bdcf64d94`
Date: 2026-07-30. Governing: captstreasurechest docs/16_V0_5_POST_AUDIT_RELEASE_WORKFLOW.md (Phase C).

## Artifacts built (Build 1, authoritative)
| Artifact | SHA-256 |
|---|---|
| capt_solo-0.5.0-py3-none-any.whl | 8889ead6664cb90bd479fbaac2aac3db214a82a5ee049950ee3ed99b4c114a53 |
| capt_solo-0.5.0.tar.gz (sdist) | a257662115c66c8f6f87cc5b2e75238e25c2e734f6e891a0c472e2209658ee8b |
| capt_core_v0.5_external.tar.gz (git archive) | 159ebbf03d16a7765cdd35c5fa8ddaac848c1c9a39dcde91f556b71808c9f3a1 |

Checksums: `release_artifacts/SHA256SUMS.txt`.

## Build environment
- Python 3.12.13
- setuptools 83.0.0 (Build 1) / 82.0.1 (Build 2)
- build backend: setuptools.build_meta
- OS: macOS 26.4.1 arm64
- build tool: build 1.5.0

## Two independent builds
Build 1: repo `.venv` (setuptools 83.0.0). Build 2: separate fresh venv
`/tmp/build2env` (setuptools 82.0.1). Both from the same candidate SHA
`be28635`, clean trees.

## Comparison
| Field | Build 1 | Build 2 | Differs? |
|---|---|---|---|
| wheel SHA-256 | 8889ead… | 91e6276… | YES (metadata) |
| sdist SHA-256 | a257662… | e8be69c… | YES (metadata) |
| file set (wheel) | 111 files | 111 files | NO |
| recursive content diff (non-dist-info) | — | — | EMPTY |
| recursive content diff (sdist, non-egg-info) | — | — | EMPTY |
| entry points | capt=capt_cli:main | identical | NO |
| dependencies | pyyaml>=5.4 | identical | NO |

## Differing fields (explained, non-semantic)
1. `dist-info/WHEEL`: `Generator: setuptools (83.0.0)` vs `(82.0.1)` — build
   tool version string only.
2. `dist-info/RECORD`: SHA-256 of the WHEEL file (derived from #1).
3. Archive-level timestamps / file ordering (tar/zip container metadata).

## Conclusion
The two builds are **semantically identical**. Every executable and semantic
content file is byte-identical. The only differences are non-executable
metadata (setuptools version string, archive timestamps). This satisfies the
workflow's reproducibility requirement: nondeterministic fields are identified
and proven to contain no executable or semantic difference.

## Immutability note
The artifact set (wheel + sdist + external tarball + checksums + manifest) is
retained under `release_artifacts/` and is the immutable release artifact for
the remainder of the audit. No rebuild after downstream testing begins.
