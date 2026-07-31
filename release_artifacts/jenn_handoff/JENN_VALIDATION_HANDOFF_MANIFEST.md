# JENN_VALIDATION_HANDOFF_MANIFEST — Phase F

Candidate SHA: `be2863508e47c3cb9ea4b4320ebab29bdcf64d94`
Date: 2026-07-30. Governing: captstreasurechest docs/16_V0_5_POST_AUDIT_RELEASE_WORKFLOW.md (Phase F).

## Purpose
Provide Jenn (external first-time user) with ONLY the materials needed to
install and evaluate CAPT Core v0.5.0. No internal convergence reports, private
architecture notes, repository paths, undocumented commands, or developer
environment configuration are included.

## Handoff bundle
- Archive: `release_artifacts/jenn_validation_handoff.tar.gz`
- SHA-256: `a9c99e8bdf29698e28d6cae0ba77fafff47961fb89e05e72d9410ad0d2594a09`

## Contents (all public)
| File | SHA-256 |
|---|---|
| capt_core_v0.5_external.tar.gz (source) | 159ebbf03d16a7765cdd35c5fa8ddaac848c1c9a39dcde91f556b71808c9f3a1 |
| capt_solo-0.5.0-py3-none-any.whl | 8889ead6664cb90bd479fbaac2aac3db214a82a5ee049950ee3ed99b4c114a53 |
| capt_solo-0.5.0.tar.gz (sdist) | a257662115c66c8f6f87cc5b2e75238e25c2e734f6e891a0c472e2209658ee8b |
| README.md | b6b1186cb8b26b5fa15b1d791a425c66f608c10893aa437f6d5208347a85db21 |
| PUBLIC_ARCHITECTURE.md | 6267474a7f7d7ae7e9f3ffca26e3fdaf01cd60ae5bdb312e17a7067e097b88f0 |
| DESIGN.md | 802ceed01e6f6900a874d8f84bc96f10f40207cc93e396ec7c0742164e40edfa |
| WHITEPAPER.md | 56824384f1e4bfa50cae0a86a1353c05a985892f950fc674ab825953ddb518ff |
| RELEASE_SECURITY_REPORT_V0.5.md | 48e87513d3a66a9a933c2388933cdf95bcc96dd95e2f30fe82ab93ffcd51f1fc |
| RELEASE_VERIFICATION_V0.5.md | 5edb8aaf4bb465c06542908b32c3f8809cd8b8acf796075df1cb348710fc9f59 |
| FIRST_TIME_USER_VALIDATION_TEMPLATE.md | 6e633571f57f44fe55d0169f9ffaf98c27965265606dedc2b74a97bed63731ee |
| SHA256SUMS.txt | (checksums for all above) |

## Explicitly EXCLUDED (per workflow §9.1)
- Internal convergence reports (`docs/convergence/*`)
- Private architecture notes / Treasure Chest content
- Repository paths (`/Users/knowurknot/capt-solo/...`)
- Undocumented commands
- Preconfigured developer environment
- Live coaching before Jenn records a block

## Instructions for Jenn
1. Verify `jenn_validation_handoff.tar.gz` checksum.
2. Extract; read README.md + FIRST_TIME_USER_VALIDATION_TEMPLATE.md.
3. Install from the wheel; complete the task sheet; record observations.
4. Return the completed observation form (unedited) as evidence.

## Status
Bundle prepared. Workflow requires STOP here and report that the external-user
phase requires Jenn. Do NOT fabricate external-user results. Do NOT perform
triple recursion (Phase G) until Jenn's genuine observations are returned and
committed as evidence.
