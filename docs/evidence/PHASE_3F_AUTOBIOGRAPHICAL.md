# Phase 3F — Canonical Autobiographical Memory

**Branch:** integration/full-public-architecture
**Date:** 2026-07-26
**Issue:** #5
**Preceded by:** Phase 3E (commit bf105ca)

## Objective
Implement autobiographical memory as an integration over identity, episodic,
semantic, and temporal memory — not an unbounded diary dump. Must be:
identity-linked, evidence-linked, temporally ordered, uncertainty-aware,
consent-aware, revisable without silently erasing prior interpretations,
distinguish observation from inference, retain conflicting interpretations,
exportable, migratable, locally stored by default.

## Implementation — `capt_solo/memory/autobiographical.py`
- `AutobiographicalMemory` backed by `MemoryEngine` (namespace `autobiographical`,
  tier `autobiographical`), reusing canonical fields (identity_link, evidence_refs,
  uncertainty, consent, provenance, metadata). No duplicate persistence (I-12).
- `AutoEntry` dataclass: subject_identity, kind (observation/inference/event/
  period/relationship/theme), content, timestamp, confidence, uncertainty,
  provenance, source_episodes, source_evidence, revision_of, superseded_by,
  conflicts_with, consent, lifecycle_state.
- `add_entry(...)`: validates identity/kind/confidence/uncertainty; pins the
  memory_id to the generated `entry_id` via the new `MemoryEngine.store(
  memory_id=...)` parameter (added in this phase — backward-compatible) so the
  canonical entry id matches the stored record.
- **Observation vs inference:** inference/theme entries are marked
  `provenance="inference"` (unless an explicit provenance is supplied) so inferred
  meaning is never silently treated as fact. No psychological truth is claimed.
- **Revision without erasure:** `revise()` creates a NEW entry linked via
  `revision_of` / `superseded_by`; the prior interpretation is retained and
  reachable via `revision_history()` (walks the chain back to the original).
- **Conflicting interpretations retained:** `mark_conflict()` links two entries
  side by side; neither is deleted.
- `list_entries` filters by subject_identity and kind; `delete_entry` supported;
  export/import round-trip verified via the engine's canonical export.

## Engine change (supporting)
- `MemoryEngine.store(...)` gained an optional `memory_id` parameter (backward-
  compatible). When supplied, the stored record uses that id instead of a
  generated uuid. This lets callers pin canonical ids (autobiographical entries,
  and any future subsystem needing stable ids). No existing call sites changed.

## Tests added
`tests/test_phase3f_autobiographical.py` (8):
- entry identity/evidence linkage
- observation vs inference distinction (provenance marking)
- revision retains prior (superseded_by / revision_of, history walk)
- conflicting interpretations retained (no deletion)
- uncertainty range validation
- list by subject and kind
- export/import persistence round-trip
- delete

## Verification
- `pytest`: 423 passed (was 415).
- `verify_runtime.py`: 46/46 pass (unchanged).

## Result
Autobiographical memory is a real, tested canonical subsystem satisfying all
required properties. Ready for Phase 3G (Knowledge / Evidence / Trust / Proof /
Governance convergence).
