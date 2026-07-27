# Phase 3D — Canonical Episodic Memory and ECHO Convergence

**Branch:** integration/full-public-architecture
**Date:** 2026-07-26
**Issue:** #5
**Preceded by:** Phase 3C (commit a605982)

## Objective
Resolve the split between CAPT SessionStore, bioCAPT ECHO, and the canonical
Episodic Memory architecture. Canonicalize the subsystem without replacing
SessionStore with ECHO.

## Approach
- **SessionStore preserved.** `capt_solo/lifecycle/sessions.py` (longitudinal
  *project* memory) is NOT replaced. It remains the session subsystem.
- **New canonical `capt_solo/memory/episodic.py`** — `EpisodicMemory` is the
  canonical Layer 3 episodic store. It is backed by `MemoryEngine`, reusing the
  canonical `MemoryRecord` fields added in Phase 3C (identity_link, evidence_refs,
  uncertainty, retention, consent). No duplicate persistence layer (I-12).
- **ECHO compatibility via clean implementation.** The external ECHO source
  (`biocapt-v2-desktop/...`) was NOT copied. Useful ECHO semantics (first-class
  episodes, explicit event ordering, replay eligibility, consolidation
  eligibility) were implemented cleanly from the approved canonical interface.
  This avoids the licensing gate [L] entirely — there is no external source
  adoption to authorize.

## Canonical Episodic Memory API
- `create_episode(*, context, identity_link, evidence_refs, confidence,
  uncertainty, retention, consent, events)` → `Episode`
- `append_event(episode_id, event)` → `Episode` (sequence auto-assigned)
- `get_episode(episode_id)` → `Optional[Episode]`
- `list_episodes(*, identity_link, namespace, limit)` → `List[Episode]`
- `mark_replay_eligible` / `mark_consolidation_eligible`
- `delete_episode(episode_id)`
- `to_canonical(episode_id)` → `MemoryRecord` (single mapping via the Phase 3C
  adapter; I-12)

Episodes are stored in the `episodic` namespace with `tier='episodic'` and a
structured `metadata` payload (events, context, eligibility flags). Event ordering
is explicit via `EpisodeEvent.sequence`.

## Tests added
`tests/test_phase3d_episodic.py` (9):
- create episode carries canonical fields (identity/evidence/uncertainty/consent)
- event ordering preserved across append
- uncertainty range-validated
- replay + consolidation eligibility flags
- list by identity linkage
- canonical retrieval (MemoryRecord mapping)
- persistence via export/import round-trip
- delete episode
- SessionStore compatibility (episodes isolated in episodic namespace)

## Verification
- `pytest`: 9 new passed; full suite **398 passed** (was 389).
- `verify_runtime.py`: 46/46 pass (unchanged).

## Result
The canonical Episodic Memory subsystem exists, is tested, reuses the hardened
memory substrate, and is ECHO-compatible without copying external source. SessionStore
remains intact. Ready for Phase 3E (Replay, Consent, Local Synchronization).
