# PUBLIC_DOC_TRUTH_AUDIT — CAPT_core Public Repository

Generated: 2026-07-30
Scope: release-facing + user-facing documents in CAPT_core (integration baseline
`cdc1bcc`). Rule per Treasure Chest doc 00: no stale SHAs, test totals, artifact
hashes, release decisions, or package inventories.

## Document-by-document

| Doc | Factual accuracy | Implementation alignment | Release-state accuracy | Stale claims | Disposition |
|-----|------------------|--------------------------|------------------------|--------------|-------------|
| README.md | ACCURATE | aligned | honest ("pre-release, not approved") | none found | KEEP; good 2-min test |
| CHANGELOG.md | ACCURATE (historical) | aligned | references v0.4.1 only as history | "v0.4.1" @ L81/112 is historical context, not current claim | DOCUMENTATION REQUIRED: clarify v0.4.1 refs are historical |
| CURRENT_STATE.md | INACCURATE | n/a | **STALE: `candidate_sha: UNFROZEN`** contradicts frozen manifest (3888f08) | yes (UNFROZEN) | DOCUMENTATION REQUIRED: update to frozen SHA |
| CHECKPOINT.md | ACCURATE | n/a | references 3888f08 (correct source) | none | KEEP |
| RELEASE_STATE.md | INACCURATE | n/a | **STALE: `candidate_sha: UNFROZEN`** | yes (UNFROZEN) | DOCUMENTATION REQUIRED: update to frozen SHA |
| TASK_QUEUE.md | ACCURATE | n/a | no SHA claims | none | KEEP |
| CAPT_CANON.md | ACCURATE | aligned | no SHA claims | none | KEEP (constitution) |
| PUBLIC_ARCHITECTURE.md | ACCURATE | aligned (six pillars) | n/a | none | KEEP |
| PUBLIC_API_STABILITY.md | ACCURATE | aligned (tiers) | n/a | none | KEEP |
| API.md | ACCURATE | aligned | n/a | none | KEEP |
| CLI.md | ACCURATE | aligned | n/a | none | KEEP |
| SECURITY.md | ACCURATE | partial (no final scan) | n/a | none | DOCUMENTATION REQUIRED: state security closure pending |
| EXTENDING.md | ACCURATE | aligned | n/a | none | KEEP |
| PLUGIN_GUIDE.md | ACCURATE | aligned | n/a | none | KEEP |
| SKILL_GUIDE.md | ACCURATE | aligned | n/a | none | KEEP |
| ROADMAP.md | ACCURATE | n/a | v0.5 listed as target | none | KEEP |
| architecture/registry.yaml | ACCURATE | aligned (70 caps) | n/a | none | KEEP (authoritative) |
| PUBLIC_API_MANIFEST_V0.5.json | ACCURATE | aligned | **correct: candidate_sha=3888f08** | none | KEEP (source of truth for freeze) |

## Key stale-claim findings (Treasure Chest doc 00 violations)

1. **CURRENT_STATE.md / RELEASE_STATE.md: `candidate_sha: UNFROZEN`**
   - The Option A correction froze candidate_sha to `3888f08` in
     PUBLIC_API_MANIFEST_V0.5.json. These two state docs were not updated.
   - Severity: DOCUMENTATION REQUIRED (misleading release-state language).
   - Fix: set candidate_sha to `3888f08e3dc054c67f79114f60c55c4aab5da687` and
     status to "FROZEN (Option A)".

2. **CHANGELOG.md: v0.4.1 references**
   - Lines 81/112 reference v0.4.1 in historical recovery context. Not a false
     current claim, but could confuse. Clarify as historical.

3. **SECURITY.md: no statement that security closure is pending**
   - The Treasure Chest requires exact-SHA security closure (doc 07). SECURITY.md
     should state the closure status honestly (pending final scan).

## Omitted shipped capabilities (internal, not public-promoted)
- ClaimGuard, Governance, Knowledge Bubbles, Skill Foundry, Proof Engine are
  implemented in `capt_solo/foundry/` but NOT in the public manifest's
  stable/experimental lists. Per the review spec, internal modules should NOT be
  auto-promoted. However, SECURITY.md / API.md could note their existence as
  internal capabilities. DOCUMENTATION REQUIRED (optional, low priority).

## Inconsistent stability tiers
- None found. PUBLIC_API_STABILITY.md tiers match the manifest.

## Inconsistent terminology
- "CAPT Core" vs "CAPT Solo" vs "Space" — the Treasure Chest (doc 15) requires
  these be kept distinct. Current docs use CAPT Core consistently; "Space" is not
  yet in public docs (because it's unimplemented). No active inconsistency, but
  the Space terminology must NOT appear as implemented.

## Verdict
The public docs are substantially honest and accurate for the SIX-PILLAR surface.
Two concrete stale-release-state defects (UNFROZEN in CURRENT_STATE/RELEASE_STATE)
must be corrected before any public claim of readiness. No public doc falsely
claims GA/final. README correctly says pre-release.
