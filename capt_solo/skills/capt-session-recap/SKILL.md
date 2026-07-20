---
name: capt-session-recap
description: End-of-session recap — summarize what was done and store it as a memory for future continuity.
---

# CAPT Solo — End-of-Session Recap

Use this skill at the end of a working session to leave a clean handoff for
future-you (or a teammate).

## When to use
- You are about to stop for the day.
- A session produced decisions, fixes, or knowledge worth keeping.

## Steps
1. Write a recap memory:
   - Tool: `capt_store_memory`
   - `namespace`: the project slug
   - `tags`: `["recap", "<date>"]`
   - `content`:
     ```
     Goal: <what this session aimed to do>
     Done: <bullet list of completed items>
     Open: <bullet list of loose ends>
     Next: <first step next session>
     ```
   - `provenance`: `"session-recap-skill"`
   - `confidence`: `1.0`
2. Export the project so the recap is included in the portable snapshot:
   - Tool: `capt_export_project`

## Pitfalls
- Keep "Open" and "Next" specific — vague recaps are useless in 3 weeks.
- Export AFTER storing the recap so it's in the snapshot.

## Verification
`capt_search_memory` with `query` = `recap <date>` returns the session summary.
