---
name: capt-bootstrap
description: Bootstrap a new project with CAPT Solo — initialize local runtime, store first memory, verify health.
---

# CAPT Solo — Project Bootstrap

Use this skill when starting a new project and you want CAPT Solo's local memory,
transactions, and message bus ready to go.

## When to use
- Starting any new codebase you want CAPT Solo to track.
- After a fresh install of the capt-solo plugin.

## Steps
1. Verify the runtime is healthy:
   - Tool: `capt_health`
   - Expect `status: "ok"`.
2. Store a project-root memory so future sessions know what this project is:
   - Tool: `capt_store_memory`
   - `content`: one sentence describing the project
   - `namespace`: the project slug (e.g. `my-app`)
   - `tags`: `["project", "bootstrap"]`
   - `provenance`: `"bootstrap-skill"`
   - `confidence`: `1.0`
3. Confirm it landed:
   - Tool: `capt_search_memory` with `query` = your project slug.
   - Expect at least one result.

## Pitfalls
- Do NOT put secrets in `content` or `metadata`. CAPT Solo stores everything
  locally in plaintext SQLite.
- If `capt_health` returns `status: "degraded"`, run the installer's
  `verify.sh` before continuing.

## Verification
After bootstrap, `capt_search_memory` for your namespace returns the seed memory.
