# BACKUP_DELTA_REPORT — capt-core-v05-hardening-backup

Generated: 2026-07-30
Method: read-only git comparison of preservation remote vs integration baseline.
No checkout, merge, or modification.

## Backup repository identity
- Owner: knowurknottty
- Visibility: private
- Default branch: `codex/capt-v0.5-p0-release-hardening` @ `a04b6fc3003ed7a01ee05117d92b715c1ec272a1`
- Role: preservation / forensic snapshot (authority level 6)
- Created empty, then pushed existing CAPT history (no reconciliation merge).

## Branches on backup remote
| Branch | HEAD | Relation to baseline `cdc1bcc` |
|--------|------|-------------------------------|
| codex/capt-v0.5-p0-release-hardening | a04b6fc | ANCESTOR (0 unique commits) |
| integration/capt-v05-release-corrected | cdc1bcc | SAME as local baseline |
| preservation/security-fixes-706-pass | 3888f08 | ANCESTOR (source commit) |
| codex/cve-v0.2-operational-continuity | 51eda9a | ANCESTOR |
| tag v0.4.0 | 8af4670 | historical |

## Commit-level delta
- `a04b6fc..cdc1bcc`: 0 commits unique to backup, 7 commits unique to baseline.
  → The backup default branch is a STRICT SUBSET of the baseline. No unmerged
    implementation exists on the backup.
- `3888f08` (source commit) and `51eda9a` (cve-v0.2) are both ancestors of baseline.
  → All security fixes and CVE-continuity docs already incorporated.

## File-level delta (baseline vs backup default)
`git diff --stat cdc1bcc a04b6fc` shows ONLY DELETIONS from the backup's perspective
(38 files, -2914 lines). These are artifacts present in baseline but absent in the
old backup snapshot:
- docs/release/* (BRANCH_CENSUS, CANDIDATE_FREEZE_PROTOCOL, CANDIDATE_IDENTITY_DESIGN_REVIEW,
  DOCUMENTATION_BOUNDARY, IMPLEMENTATION_GAP_MATRIX, PUBLIC_RELEASE_GAP_REPORT,
  RELEASE_BACKLOG, RELEASE_INTEGRATION_PLAN) — our review/integration docs (newer than backup).
- tests/test_release_identity_option_a.py, test_release_semantics.py (modified),
  test_architecture_cli_degradation.py, test_checkpoint_test_status_integrity.py,
  test_doctor_sh_command_injection.py, test_release_candidate_sha_provenance.py,
  test_verification_evidence_integrity.py, test_verification_identity_untracked.py,
  test_verification_routing_content_change.py — our Option A + security tests.
- doctor.sh (4 lines changed), PUBLIC_API_MANIFEST_V0.5.json (2 lines).

Interpretation: the backup predates our Option A correction + review pass. It has
NO content the baseline lacks.

## Unique backup evidence (forensic value only)
- The backup preserves the PRE-INCIDENT state at `a04b6fc` — proof that the SHA-loop
  incident had not yet occurred when this snapshot was taken. This is historical
  evidence of the incident timeline, not implementation.
- `preservation/security-fixes-706-pass` @ `3888f08` is the immutable source commit
  (706 tests passed). This is the canonical source commit referenced by Option A.
- `codex/cve-v0.2-operational-continuity` preserves CVE operational docs.

## ATE / security-CI content
- The ATE hardening branches (`hardening/post-merge-release-gates-clean` etc.) are
  NOT on the backup remote. They exist on `origin` (CAPT_core) `hardening/*` and
  locally. Therefore the backup does NOT contain the ATE component, gitleaks, or
  release-security CI. Those are recoverable from CAPT_core `origin` directly
  (see BATCH1_CHERRYPICK_IMPACT.md).
- Conclusion: no unique backup work must be recovered for the ATE cherry-pick.

## Disposition
- The backup is archival-only. No commit, file, or security fix in it is missing
  from the baseline.
- Recommended action: KEEP the backup as forensic preservation. Do not merge, do
  not cherry-pick from it (nothing unique). Reference `3888f08` as the source
  commit authority.
- History that should remain archival only: the pre-incident `a04b6fc` snapshot
  (documents the incident baseline); the looped metadata commits (historical
  artifacts of the SHA-loop incident, already superseded by Option A).
