# INSTALLED_VS_REPOSITORY_EVIDENCE_MATRIX — Phase E

Candidate SHA: `be2863508e47c3cb9ea4b4320ebab29bdcf64d94`

| Claim / conclusion | Installed artifact can prove it? | Repository needed? | Classification |
|---|---|---|---|
| Version 0.5.0 | YES | no | INSTALLED_ARTIFACT_EVIDENCE |
| Package inventory (19 subpkgs) | YES (wheel RECORD) | no | INSTALLED_ARTIFACT_EVIDENCE |
| ATE component present | YES (wheel RECORD) | no | INSTALLED_ARTIFACT_EVIDENCE |
| CLI `capt` entry point | YES | no | INSTALLED_ARTIFACT_EVIDENCE |
| `capt doctor` works | YES (runtime) | no | RUNTIME_EVIDENCE |
| No-network import | YES (runtime) | no | RUNTIME_EVIDENCE |
| Zero Hermes import | YES (grep installed pkg) | no | RUNTIME_EVIDENCE |
| LICENSE shipped | YES (dist-info/licenses) | no | INSTALLED_ARTIFACT_EVIDENCE |
| Self-contained (no repo) | YES | no | INSTALLED_ARTIFACT_EVIDENCE |
| Public API manifest matches inventory | NO (manifest not in wheel) | YES (Phase B) | UNPROVEN from installed / REPOSITORY_ONLY for agreement |
| Release validator passes | NO (needs repo docs) | YES (Phase B) | REPOSITORY_ONLY_EVIDENCE |
| Exact-SHA reports correct | NO | YES | REPOSITORY_ONLY_EVIDENCE |
| Convergence audit findings | NO | YES | REPOSITORY_ONLY_EVIDENCE |

## Principle
An end user with only the wheel + public docs can verify: version, packages,
ATE presence, CLI, doctor, local-first behavior, LICENSE. They CANNOT verify
from the installed artifact alone: the release validator result, the exact-SHA
reports, or the convergence audit — those require the source repository and are
correctly classified as REPOSITORY_ONLY_EVIDENCE. This matrix prevents the
self-audit from overclaiming.
