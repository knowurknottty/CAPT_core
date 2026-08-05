# CAPT Standalone Harness v0.5 — Release Evidence Manifest

Date: 2026-08-05
Candidate SHA: b45c4b005c9171172d055697a55034006bb0f2fe
Repair SHA: b79c4f05784d001268e3fef523755365b1f5888e
Attribution: knowurknot

## Artifact Inventory

| # | Vault Path | Source Path | SHA-256 | Size | Candidate SHA | Evidence Type | Capability | Trust Class | Sanitized | Notes |
|---|------------|-------------|---------|------|---------------|---------------|------------|-------------|-----------|-------|
| 1 | 00 — Audit Index.md | This session | N/A (generated) | — | b79c4f0 | DERIVED_ANALYSIS | Master index | DERIVED_ANALYSIS | YES | Generated from evidence files |
| 2 | 01 — VerificationResult Defect.md | This session | N/A (generated) | — | b79c4f0 | DERIVED_ANALYSIS | Verification contract | DERIVED_ANALYSIS | YES | Documents defect + repair |
| 3 | 02 — Harness Functionality.md | This session | N/A (generated) | — | b79c4f0 | DERIVED_ANALYSIS | All capabilities | DERIVED_ANALYSIS | YES | Capability classification matrix |
| 4 | 03 — Model Operator.md | This session | N/A (generated) | — | b79c4f0 | DERIVED_ANALYSIS | Model operator | DERIVED_ANALYSIS | YES | Authority boundary assessment |
| 5 | 04 — Test Evidence.md | This session | N/A (generated) | — | b79c4f0 | DERIVED_ANALYSIS | Test/quality | DERIVED_ANALYSIS | YES | Test results and contract probes |
| 6 | 05 — Public Claim Audit.md | This session | N/A (generated) | — | b79c4f0 | DERIVED_ANALYSIS | Public claims | DERIVED_ANALYSIS | YES | INCOMPLETE AUDIT |
| 7 | 06 — Treasure Chest.md | This session | N/A (generated) | — | b79c4f0 | DERIVED_ANALYSIS | Treasure chest | DERIVED_ANALYSIS | YES | INCOMPLETE AUDIT |
| 8 | 07 — Branch Shadow.md | This session | N/A (generated) | — | b79c4f0 | DERIVED_ANALYSIS | Git state | DERIVED_ANALYSIS | YES | Branch shadow reconciliation |
| 9 | 08 — Release Evidence Manifest.md | This session | N/A (generated) | — | b79c4f0 | DERIVED_ANALYSIS | Evidence | DERIVED_ANALYSIS | YES | This document |
| 10 | 09 — Residual Backlog.md | This session | N/A (generated) | — | b79c4f0 | OPERATOR_HANDOFF | Backlog | OPERATOR_HANDOFF | YES | Post-release work items |
| 11 | 10 — Canonical Handoff.md | This session | N/A (generated) | — | b79c4f0 | OPERATOR_HANDOFF | Handoff | OPERATOR_HANDOFF | YES | Exact reproduction commands |
| 12 | 11 — Validation Report.md | This session | N/A (generated) | — | b79c4f0 | DERIVED_ANALYSIS | Validation | DERIVED_ANALYSIS | YES | Package self-validation |
| 13 | evidence/full-suite.log | /tmp/capt-release-evidence-b45c4b0*/full-suite.log | (see below) | 916 bytes | b45c4b0 | PRIMARY_EXECUTION_EVIDENCE | Test suite | PRIMARY | YES | 766 passed, 12 deselected |
| 14 | evidence/verify-verification-fix.log | /tmp/capt-verify-verification-fix.log | (see below) | 26717 bytes | b79c4f0 | PRIMARY_EXECUTION_EVIDENCE | Test suite post-repair | PRIMARY | YES | 766 passed, 12 deselected, exit 0 |
| 15 | evidence/git-head.txt | /tmp/capt-release-evidence-b45c4b0*/git-head.txt | N/A | 41 bytes | b45c4b0 | SOURCE_STATE_EVIDENCE | Git identity | SOURCE | YES | b45c4b005c91... |
| 16 | evidence/git-log.txt | /tmp/capt-release-evidence-b45c4b0*/git-log.txt | N/A | 574 bytes | b45c4b0 | SOURCE_STATE_EVIDENCE | Commit chain | SOURCE | YES | 8 commits |
| 17 | evidence/git-status.txt | /tmp/capt-release-evidence-b45c4b0*/git-status.txt | N/A | 0 bytes | b45c4b0 | SOURCE_STATE_EVIDENCE | Worktree status | SOURCE | YES | Empty (clean) |
| 18 | evidence/evidence-manifest.md | /tmp/capt-release-evidence-b45c4b0*/evidence-manifest.md | N/A | 7414 bytes | b45c4b0 | DERIVED_ANALYSIS | Evidence manifest | OPERATOR_HANDOFF | YES | Prior session manifest |
| 19 | evidence/execution-limitation-statement.md | /tmp/capt-release-evidence-b45c4b0*/execution-limitation-statement.md | N/A | 3218 bytes | b45c4b0 | OPERATOR_HANDOFF | Limitations | OPERATOR_HANDOFF | YES | Documented limitations |
| 20 | evidence/release-decision.md | /tmp/capt-release-evidence-b45c4b0*/release-decision.md | N/A | 4500 bytes | b45c4b0 | OPERATOR_HANDOFF | Release verdict | OPERATOR_HANDOFF | YES | Terminal verdict |
| 21 | evidence/operator-handoff.md | /tmp/capt-release-evidence-b45c4b0*/operator-handoff.md | N/A | 5372 bytes | b45c4b0 | OPERATOR_HANDOFF | Operator commands | OPERATOR_HANDOFF | YES | Exact zsh commands |
| 22 | evidence/residual-backlog.md | /tmp/capt-release-evidence-b45c4b0*/residual-backlog.md | N/A | 3034 bytes | b45c4b0 | OPERATOR_HANDOFF | Backlog | OPERATOR_HANDOFF | YES | Prior backlog |
| 23 | evidence/version-map.md | /tmp/capt-release-evidence-b45c4b0*/version-map.md | N/A | 2428 bytes | b45c4b0 | DERIVED_ANALYSIS | Version axes | OPERATOR_HANDOFF | YES | Version axis authority |
| 24 | evidence/adversarial-battery.py | /tmp/capt-release-evidence-b45c4b0*/installed/adversarial-battery.py | N/A | 3675 bytes | b45c4b0 | INSTALLED_ARTIFACT_EVIDENCE | Authority matrix | INSTALLED | YES | Socket paths redacted |
| 25 | evidence/model-artifacts-sha256.txt | /tmp/capt-release-evidence-b45c4b0*/artifacts/model-artifacts-sha256.txt | N/A | 579 bytes | b45c4b0 | PRIMARY_EXECUTION_EVIDENCE | Model artifacts | PRIMARY | YES | 3 artifact digests |
| 26 | evidence/wheel-sha256.txt | /tmp/capt-release-evidence-b45c4b0*/artifacts/wheel-sha256.txt | N/A | 177 bytes | b45c4b0 | INSTALLED_ARTIFACT_EVIDENCE | Package | INSTALLED | YES | Wheel hash |

## NOT Copied (unsafe or binary)

| Source | Reason |
|--------|--------|
| artifacts/capt_solo-0.5.0-py3-none-any.whl | Binary; 309KB; sha256 in wheel-sha256.txt |
| installed/ledger-*.db | Binary SQLite; contains session tokens; not safe for vault |
| /tmp/capt-*/token | Credential; never copied |
| /tmp/capt-*/runtime.sock | Socket; not a file artifact |
| /tmp/capt-*/*.db-* | WAL/SHM files; binary; transient |

## Trust Classifications Used

- PRIMARY_EXECUTION_EVIDENCE: direct output from a test or lifecycle run
- SOURCE_STATE_EVIDENCE: git state, commit metadata, worktree status
- INSTALLED_ARTIFACT_EVIDENCE: evidence from the installed wheel lifecycle
- DERIVED_ANALYSIS: documents assembled from evidence this session
- OPERATOR_HANDOFF: documents containing reproduction commands or backlog
- REPORTED_UNVERIFIED: claims not independently verified
- MISSING: artifact expected but not found
