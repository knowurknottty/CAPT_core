---
name: capt-knowledge-capture
description: Capture reusable knowledge (snippets, commands, gotchas) into CAPT Solo for future retrieval.
---

# CAPT Solo — Knowledge Capture

Use this skill to turn something you just learned into a retrievable memory.

## When to use
- You discovered a non-obvious command, config, or workaround.
- You want a personal "second brain" for project-specific knowledge.

## Steps
1. Store the knowledge nugget:
   - Tool: `capt_store_memory`
   - `namespace`: the project slug (or `general` for cross-project)
   - `tags`: `["knowledge", "<topic>"]`
   - `content`: the exact command / snippet / rule, with a one-line explanation.
   - `metadata`: `{"source": "<where you learned it>"}`
   - `provenance`: `"knowledge-capture-skill"`
   - `confidence`: `1.0` if verified, lower if untested.
2. Retrieve later:
   - Tool: `capt_search_memory` with `query` = the topic or a keyword.

## Pitfalls
- Keep `content` copy-pasteable. Don't paraphrase commands into prose.
- Tag consistently (`knowledge` + topic) so search stays precise.

## Verification
`capt_search_memory` with `query` = `<topic>` returns the nugget.
