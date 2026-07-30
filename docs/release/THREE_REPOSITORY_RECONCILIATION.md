# THREE_REPOSITORY_RECONCILIATION — CAPT Core v0.5

Generated: 2026-07-30
Reviewer: HY3 (owner-supervised, review-only)
Method: read-only inspection of three repositories + Treasure Chest clone (temp).
No merges, cherry-picks, tags, publishes, or history rewrites performed.

## Repository role table

| Repo | Visibility | Default branch | HEAD | Role | Canonical? |
|------|-----------|----------------|------|------|-----------|
| knowurknottty/CAPT_core (local `~/capt-solo`) | public (intended) | main (v0.4) | integration/capt-v05-release-corrected @ `cdc1bcc` | Active integration + release surface | YES (per Treasure Chest doc 17) |
| knowurknottty/capt-core-v05-hardening-backup | private | codex/capt-v0.5-p0-release-hardening | `a04b6fc` | Preservation/forensic snapshot | NO (preservation only) |
| knowurknottty/captstreasurechest | private | (none, folder) | n/a (GitHub repo, cloned to /tmp/tc_clone) | Operating manual / release requirements | NO (authority level 5) |

## Key determinations (Phase 1)

1. **Does CAPT_core contain the corrected Option A release implementation?**
   YES. The integration branch `integration/capt-v05-release-corrected` @ `cdc1bcc`
   contains source commit `3888f08` (security fixes, 706 tests) + metadata commit
   `1b9bf74` + test fix `be4b0da` + archaeology/review docs. The Treasure Chest
   finish-line playbook (doc 15) records exactly this checkpoint
   (source `3888f08`, metadata `be4b0da`, 715 tests, Python 3.12.13). Authority-aligned.

2. **Does the backup contain unique commits/files not in the public repo?**
   NO. `a04b6fc` (backup default) is an ANCESTOR of `cdc1bcc` (0 commits unique to
   backup, 7 commits unique to baseline). `3888f08` and `cve-v0.2` are also ancestors.
   The backup is a strict subset — preservation only, no unmerged implementation.
   (The ATE hardening branches are NOT on the backup; they live on `origin`
   `hardening/*` and are recoverable from CAPT_core directly.)

3. **Does the Treasure Chest contain requirements absent from both code repos?**
   YES — substantially. The Treasure Chest finish-line playbook (doc 15) defines a
   v0.5 contract that includes:
   - Workstream D: First-class **Space** architecture (isolation/governance boundary)
   - Workstream E: **Provider-neutral runtime adapter** contract (non-Hermes tested)
   - Workstream F: **Trust Center, Threat Model, NIST/ISO/SOC2 mappings, SBOM**
   - Workstream G/I: Documentation truth audit, FINAL_RELEASE_BLOCKERS.md
   - Doc 07: exact-SHA release-evidence files (RELEASE_SECURITY_REPORT,
     CONFORMANCE_RESULTS, ARTIFACT_MANIFEST, etc.)
   NONE of these are implemented in the public repo today. The six-pillar public
   architecture (ADR-0008) does NOT include Spaces or runtime adapters as shipped
   requirements — this is the central conflict (see below).

## Authority conflict (must be resolved by owner)

The Treasure Chest (authority level 5) says v0.5 requires Spaces + runtime adapters
+ Trust Center + exact-SHA evidence files, and its status rule is explicitly
"NOT READY — BLOCKERS REMAIN" (docs 00, 02).

The owner's live session instructions (this conversation) said: "Do not begin
implementation. Do not begin refactoring. Do not begin roadmap execution." and
treated the six-pillar public architecture as the release surface; the release
validator (Option A) was declared complete and frozen.

These are NOT silently reconcilable. Two readings:
- (A) The owner NARROWED v0.5 to the six-pillar surface + Option A after the
  Treasure Chest was written; Spaces/adapters/Trust Center are POST-v0.5.
- (B) The Treasure Chest scope still stands; v0.5 is genuinely NOT READY and the
  "feature-complete" claim was scoped only to the six pillars, not the full contract.

Recommendation: treat (A) as the working assumption for the current review (since
the owner's live instructions govern), but RECORD the full Treasure Chest contract
as the authoritative v0.5 definition and flag the scope discrepancy as OWNER_DECISION
#1. The public repo must NOT be described as "final" or "GA" under either reading.

## Cross-repo overlaps

- CAPT_core (integration branch) = the live working surface. Contains all verified
  implementation + Option A + archaeology/review docs.
- Backup = ancestor snapshot; no new content. Useful only as forensic proof of
  pre-incident state and loss-surface elimination.
- Treasure Chest = the requirement authority. Its docs 00/02/07/15 define the
  release contract and status language.

## Conclusion

The three repositories are mutually consistent on what IS implemented (Option A,
six-pillar architecture, foundry subsystems). They diverge on what v0.5 REQUIRES:
the Treasure Chest demands more than the current six-pillar surface delivers.
The release is NOT READY per the Treasure Chest's own rule. No blocking
implementation gap exists for the six-pillar surface, but the Treasure Chest's
broader contract is unmet. Owner decision required on final v0.5 scope.
