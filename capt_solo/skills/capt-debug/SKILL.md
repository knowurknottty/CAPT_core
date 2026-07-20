---
name: capt-debug
description: Debug a failing task with CAPT Solo — record the hypothesis, the failing command, and the resolution as memories.
---

# CAPT Solo — Debugging Workflow

Use this skill when you hit a bug and want a durable, searchable record of what
you tried and what fixed it.

## When to use
- A test fails, a build breaks, or runtime behavior is wrong.
- You want to avoid re-debugging the same issue in a future session.

## Steps
1. Record the symptom as a memory:
   - Tool: `capt_store_memory`
   - `namespace`: the project slug
   - `tags`: `["debug", "symptom"]`
   - `content`: exact error message + what you were doing.
2. Record each hypothesis you test:
   - Tool: `capt_store_memory`
   - `tags`: `["debug", "hypothesis"]`
   - `content`: "Tried X because Y. Result: Z."
3. When resolved, store the fix:
   - Tool: `capt_store_memory`
   - `tags`: `["debug", "fix"]`
   - `content`: the root cause and the one-line fix.
4. Link them with a correlation id via a transaction (see capt-transaction skill):
   - Tool: `capt_begin_transaction` with `correlation_id` = a short bug id.
   - Tool: `capt_commit_transaction` once the fix is verified.

## Pitfalls
- Don't store stack traces containing PII or tokens.
- Keep `confidence` honest: `1.0` only when the fix is verified by a green run.

## Verification
`capt_search_memory` with `query` = your bug id returns symptom + fix memories.
