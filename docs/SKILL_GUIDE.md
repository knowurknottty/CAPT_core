# CAPT Solo v0.1 — Skill Guide

CAPT Solo ships **8 beginner-friendly Hermes skills**. Each lives in
`capt_solo/skills/<name>/SKILL.md` and is installed to `~/.hermes/skills/<name>/`.

## The skills

| Skill | When to use |
|-------|--------------|
| `capt-bootstrap` | Start a new project: init runtime, seed a project memory, verify health. |
| `capt-debug` | Record a bug's symptom, hypotheses, and fix as memories. |
| `capt-arch-decision` | Capture an Architecture Decision Record (ADR). |
| `capt-memory-review` | Periodically prune stale/low-confidence/duplicate memories. |
| `capt-knowledge-capture` | Save a reusable command/snippet/gotcha. |
| `capt-transaction` | Wrap a multi-step side-effecting op in a CTP transaction. |
| `capt-session-recap` | End-of-session summary stored as a memory. |
| `capt-recovery` | Recover after an interruption (replay journal, verify, restore). |

## How a skill is structured

Each `SKILL.md` has YAML frontmatter and a body with:

- **When to use** — trigger conditions.
- **Steps** — numbered, referencing only public `capt_*` tools.
- **Pitfalls** — what not to do (e.g. never store secrets).
- **Verification** — how to confirm the skill did its job.

## Principles the skills follow

1. **Public tools only.** Skills never reference `MemoryEngine`, `CTPRuntime`,
   or file paths directly — they call the `capt_*` tools.
2. **No secrets.** Skills explicitly warn against storing tokens/PII.
3. **Export before destructive ops.** `capt-export-project` is called before any
   prune or restore.
4. **Verifiable.** Each skill ends with a concrete check you can run.

## Using a skill

In Hermes, invoke by name, e.g.:

```
use the capt-bootstrap skill to start my new project "ledger"
```

Hermes loads the SKILL.md and follows its steps, calling the `capt_*` tools.

## Writing a new skill

1. Create `capt_solo/skills/<name>/SKILL.md` with the frontmatter
   (`name`, `description`).
2. Body: When to use / Steps / Pitfalls / Verification.
3. Reference only `capt_*` tools.
4. Add it to the install loop in `install.sh` (the glob already picks it up
   automatically — no manual edit needed).
5. Test it manually with `./verify.sh` green first.
