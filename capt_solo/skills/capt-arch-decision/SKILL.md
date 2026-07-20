---
name: capt-arch-decision
description: Record an architectural decision with CAPT Solo — context, options, chosen approach, consequences.
---

# CAPT Solo — Architectural Decisions

Use this skill to capture Architecture Decision Records (ADRs) as memories so
design rationale survives across sessions and team members.

## When to use
- You chose a library, pattern, or structure and want the "why" preserved.
- Before a refactor that future-you might question.

## Steps
1. Store the decision:
   - Tool: `capt_store_memory`
   - `namespace`: the project slug
   - `tags`: `["adr", "<decision-slug>"]`
   - `content`:
     ```
     Decision: <what you chose>
     Context: <why it was needed>
     Options considered: <A, B, C>
     Consequences: <tradeoffs>
     ```
   - `metadata`: `{"status": "accepted"}`
   - `provenance`: `"arch-decision-skill"`
2. Cross-link related decisions by sharing a `correlation_id` through a
   transaction (see capt-transaction skill).

## Pitfalls
- One decision per memory. Don't bundle three ADRs into one record.
- Use a stable `<decision-slug>` so you can `capt_search_memory` it later.

## Verification
`capt_search_memory` with `query` = `<decision-slug>` returns the ADR.
