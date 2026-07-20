---
name: capt-memory-review
description: Review and prune CAPT Solo memories for a project — find stale, low-confidence, or duplicate entries.
---

# CAPT Solo — Memory Review

Use this skill periodically to keep the local memory store clean and useful.

## When to use
- At the end of a sprint or before a release.
- When `capt_search_memory` starts returning noisy or outdated results.

## Steps
1. List everything in the project namespace:
   - Tool: `capt_search_memory` with `query` = the project slug, or
   - Tool: `capt_get_memory` after listing (the plugin exposes list via search).
2. Flag for review:
   - `confidence` < 0.5 — likely a guess, confirm or delete.
   - `updated_at` older than the last release — verify still true.
   - Duplicate `content` across two memory ids — keep the newer, delete the older.
3. Delete confirmed-stale memories:
   - Tool: `capt_get_memory` to confirm id, then delete via the engine API
     (`MemoryEngine.delete`) — exposed through a small script if needed.
4. Export a snapshot before pruning:
   - Tool: `capt_export_project` — keeps a recoverable backup.

## Pitfalls
- Always `capt_export_project` BEFORE deleting in bulk.
- Don't delete memories another session may still reference by id.

## Verification
After review, `capt_search_memory` for the namespace returns only current,
high-signal memories.
