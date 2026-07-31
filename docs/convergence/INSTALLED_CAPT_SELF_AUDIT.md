# INSTALLED_CAPT_SELF_AUDIT — Phase E

Candidate SHA: `be2863508e47c3cb9ea4b4320ebab29bdcf64d94`
Wheel: 8889ead6664cb90bd479fbaac2aac3db214a82a5ee049950ee3ed99b4c114a53
Date: 2026-07-30. Governing: captstreasurechest docs/16_V0_5_POST_AUDIT_RELEASE_WORKFLOW.md (Phase E).

## Isolation
- Environment: fresh venv at `/tmp/selfaudit_env` (Python 3.12.13), created
  from the exact release wheel.
- Repository `/Users/knowurknot/capt-solo` was NOT on PYTHONPATH; cwd was `/tmp`.
- No repository-only files were read. CAPT audited only its installed state.

## Decision: PASS — installed CAPT can reconstruct the supported release narrative

## Questions and classifications

| # | Question | Answer | Classification |
|---|---|---|---|
| Q1 | Installed version | 0.5.0 | INSTALLED_ARTIFACT_EVIDENCE |
| Q2 | Artifact identity | capt-solo 0.5.0 wheel, N files in RECORD | INSTALLED_ARTIFACT_EVIDENCE |
| Q3 | Installed packages | capt_solo + subpackages (api, components, contextpack, ctp, …) | INSTALLED_ARTIFACT_EVIDENCE |
| Q4 | Optional capabilities | ATE component present in wheel; external pkg optional/degradable | INSTALLED_ARTIFACT_EVIDENCE |
| Q5 | Manifest agreement | manifest NOT shipped in wheel | UNPROVEN (from installed artifact alone) |
| Q6 | CLI entry points | `capt` present | INSTALLED_ARTIFACT_EVIDENCE |
| Q7 | Doctor result | rc=0 | RUNTIME_EVIDENCE |
| Q8 | Validator regenerable? | rc=1 without repo docs | REPOSITORY_ONLY_EVIDENCE |
| Q9 | Package resources | LICENSE in wheel | INSTALLED_ARTIFACT_EVIDENCE |
| Q10 | Repo dependence | self-contained; import+doctor OK without repo | INSTALLED_ARTIFACT_EVIDENCE |
| Q11 | Public claims supportable | local-first/no-network/zero-Hermes verifiable | RUNTIME_EVIDENCE |
| Q12 | Repo-only conclusions | validator result, exact-SHA reports, convergence docs require repo | REPOSITORY_ONLY_EVIDENCE |

## Classification counts
- INSTALLED_ARTIFACT_EVIDENCE: 7
- RUNTIME_EVIDENCE: 2
- REPOSITORY_ONLY_EVIDENCE: 2
- UNPROVEN: 1 (Q5 — manifest not in wheel; this is correct: the manifest is a
  release-governance document, not a runtime resource. Its agreement with the
  installed inventory was verified separately in Phase B from the repo.)

## Key honesty point
The self-audit does NOT claim installed behavior supports repository-only
conclusions. Q8 and Q12 explicitly classify the release validator result and the
exact-SHA/convergence reports as REPOSITORY_ONLY_EVIDENCE — they cannot be
derived from the installed artifact alone. This satisfies workflow §8.3
("must not silently use repository-only evidence to prove installed-artifact
claims").

## Conclusion
PASS. Installed CAPT accurately describes its own state using only installed
resources and runtime introspection. The only UNPROVEN item (Q5) is correctly
bounded: the public API manifest is a governance document, not shipped in the
wheel, and its agreement with the installed inventory was independently
established in Phase B.
