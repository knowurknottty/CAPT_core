# CAPT Standalone Harness v0.5 — Audit Package Validation Report

Date: 2026-08-05

## Files Created

| # | Document | Status |
|---|----------|--------|
| 00 | CAPT Standalone Harness v0.5 Audit Index | CREATED |
| 01 | VerificationResult Frozen-Contract Defect and Repair | CREATED |
| 02 | Standalone CAPT Core Harness Functionality Audit | CREATED |
| 03 | CAPT Model Operator Status and Authority Boundary | CREATED |
| 04 | Test, Contract, and Quality Evidence | CREATED |
| 05 | Public Claim Audit | CREATED |
| 06 | Treasure Chest Function Reconciliation | CREATED (rebuilt after quarantine) |
| 07 | Branch Shadow Reconciliation | CREATED (rebuilt after quarantine) |
| 08 | Release Evidence Manifest | CREATED |
| 09 | Residual Backlog | CREATED |
| 10 | Canonical CAPT Release Handoff | CREATED |
| 11 | Audit Package Validation Report (this document) | CREATED |
| 12 | Git Release Provenance | NOT YET GENERATED (pending git hygiene commit + push) |

## Files Quarantined

| Document | Path | Reason |
|----------|------|--------|
| 06 — Treasure Chest Function Reconciliation (draft) | _quarantine/INVALIDATED_DRAFTS/ | INVENTED_ACRONYM_EXPANSION + ABSENCE_CLAIM_WITHOUT_CANONICAL_SEARCH |
| 07 — Branch Shadow Reconciliation (draft) | _quarantine/INVALIDATED_DRAFTS/ | Stated "ALL commits LOCAL ONLY" before remote fetch was performed |

## Raw Evidence Copied

| Source | Destination | Status |
|--------|--------------|--------|
| /tmp/capt-release-evidence-b45c4b0*/full-suite.log | evidence/full-suite.log | COPIED |
| /tmp/capt-verify-verification-fix.log | evidence/verify-verification-fix.log | COPIED |
| /tmp/capt-release-evidence-b45c4b0*/git-head.txt | evidence/git-head.txt | COPIED |
| /tmp/capt-release-evidence-b45c4b0*/git-log.txt | evidence/git-log.txt | COPIED |
| /tmp/capt-release-evidence-b45c4b0*/git-status.txt | evidence/git-status.txt | COPIED |
| /tmp/capt-release-evidence-b45c4b0*/evidence-manifest.md | evidence/evidence-manifest.md | COPIED |
| /tmp/capt-release-evidence-b45c4b0*/execution-limitation-statement.md | evidence/execution-limitation-statement.md | COPIED |
| /tmp/capt-release-evidence-b45c4b0*/release-decision.md | evidence/release-decision.md | COPIED |
| /tmp/capt-release-evidence-b45c4b0*/operator-handoff.md | evidence/operator-handoff.md | COPIED |
| /tmp/capt-release-evidence-b45c4b0*/residual-backlog.md | evidence/residual-backlog.md | COPIED |
| /tmp/capt-release-evidence-b45c4b0*/version-map.md | evidence/version-map.md | COPIED |
| /tmp/capt-release-evidence-b45c4b0*/installed/adversarial-battery.py | evidence/adversarial-battery.py | COPIED (sanitized) |
| /tmp/capt-release-evidence-b45c4b0*/artifacts/model-artifacts-sha256.txt | evidence/model-artifacts-sha256.txt | COPIED |
| /tmp/capt-release-evidence-b45c4b0*/artifacts/wheel-sha256.txt | evidence/wheel-sha256.txt | COPIED |

## Hash Validation

All copied evidence files will be hashed after copying and recorded in release_evidence_manifest.json.

## Secret Scan

- adversarial-battery.py: sanitized (socket paths and token reads redacted to placeholders)
- No token, credential, or API key files copied
- No .db, .sock, or token files copied

## Contradiction Review

1. CORRECTED: Quarantined drafts classified KHSB/CTP/memory as NOT PRESENT — contradicted by direct repository tree inspection showing all modules exist and ship in the installed wheel.
2. CORRECTED: Quarantined draft stated "ALL commits LOCAL ONLY" before performing remote fetch — fetch performed; release/capt-standalone-final confirmed absent from origin (local-only claim now evidence-backed).
3. CORRECTED: SHA scoping — documents now distinguish PRE_REPAIR_INSTALLED_CANDIDATE_SHA (b45c4b0) from VERIFICATION_REPAIR_SHA (b79c4f0) from CURRENT_LOCAL_HEAD (b79c4f0).
4. CORRECTED: Model operator classification — documents now distinguish "bounded read-only inspection proven" from "general model-driven engineering unproven" with full commit chain reconciliation.

## Audit Failure Modes

| Mode | Status | Description |
|------|--------|-------------|
| INVENTED_ACRONYM_EXPANSION | ENCOUNTERED, CORRECTED | Invented expansions for KHSB and CTP before finding canonical definitions |
| ABSENCE_CLAIM_WITHOUT_CANONICAL_SEARCH | ENCOUNTERED, CORRECTED | Classified modules as absent based on zero search-tool results without tree inspection |

## Validation Result

- All created documents: VALIDATED
- Raw evidence: COPIED (pending hash verification)
- JSON manifest: PENDING (will be written after evidence copy)
- Broken links: NONE (Obsidian wikilinks resolve within package)
- Secret patterns: NONE (sanitized)
- Contradictory verdicts: CORRECTED (quarantined drafts invalidated)
- Candidate SHAs: CORRECTLY SCOPED (pre-repair vs repair vs current vs final not-yet-populated)
- Local-only commits: LABELED LOCAL ONLY
- Reported evidence: NOT upgraded to verified evidence
- Missing artifacts: MARKED MISSING or NOT YET GENERATED
