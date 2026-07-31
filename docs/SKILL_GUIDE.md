# CAPT Solo Skill Guide

**Use repeatable CAPT workflows in Hermes without memorizing the underlying tool calls.**

A CAPT skill is a guided procedure written for humans first and executed through public `capt_*` tools.

## Start here

In Hermes, invoke a skill by name:

```text
Use the capt-bootstrap skill to start my new project "ledger".
```

Hermes loads the skill instructions, follows the steps, calls supported CAPT tools, and finishes with a verification check.

## Which skill should I use?

| Goal | Skill |
|---|---|
| Start a new CAPT-backed project | `capt-bootstrap` |
| Record and work through a bug | `capt-debug` |
| Capture an architecture decision | `capt-arch-decision` |
| Review stale or low-confidence memory | `capt-memory-review` |
| Save a reusable command, snippet, or lesson | `capt-knowledge-capture` |
| Wrap a risky multi-step operation in a transaction | `capt-transaction` |
| Save an end-of-session recap | `capt-session-recap` |
| Recover after interruption | `capt-recovery` |

## What every skill contains

Each `SKILL.md` includes:

- **When to use** — the trigger or situation
- **Steps** — the procedure using public CAPT tools
- **Pitfalls** — unsafe or misleading actions to avoid
- **Verification** — a concrete check that confirms the procedure worked

That structure keeps a skill understandable before it is executed.

## Safety rules

CAPT skills follow four rules:

1. **Use public tools only.** Skills call `capt_*` tools instead of internal classes or raw storage paths.
2. **Do not store secrets.** Tokens, credentials, private keys, and unnecessary sensitive data do not belong in CAPT memory.
3. **Preserve state before destructive work.** Export or back up before pruning, restoring, or replacing persistent data.
4. **End with evidence.** Every skill finishes with a check rather than a vague success statement.

## Example workflows

### Start a project

```text
Use capt-bootstrap to initialize the project "ledger", save its purpose, and verify CAPT health.
```

### Capture a decision

```text
Use capt-arch-decision to record why we chose SQLite for local persistence, including alternatives and tradeoffs.
```

### Perform a governed operation

```text
Use capt-transaction to wrap the release publication steps. Abort if any validation fails.
```

### Recover after interruption

```text
Use capt-recovery to inspect pending transactions, verify the journal, and restore the last safe checkpoint.
```

## Writing a new skill

Create:

```text
capt_solo/skills/<name>/SKILL.md
```

Use this shape:

```markdown
---
name: your-skill-name
description: One sentence describing when this skill helps.
---

# Your Skill

## When to use

Describe the trigger.

## Steps

1. Call a public `capt_*` tool.
2. Record important evidence or state.
3. Stop or abort when a required check fails.

## Pitfalls

- Do not store secrets.
- Do not bypass public tools.

## Verification

Describe the exact result or receipt that proves completion.
```

Then:

1. Reference only public `capt_*` tools.
2. Include failure and rollback behavior where relevant.
3. Run the repository verification commands.
4. Test the skill manually in Hermes.

The installer discovers skill directories automatically.

## Review checklist

Before publishing a skill, confirm:

- the trigger is obvious
- the steps are short and ordered
- consequential actions have transaction boundaries
- unsafe inputs are rejected
- secrets are excluded
- rollback or recovery is described
- the final claim is supported by a concrete check

## Related documentation

- [Plugin Guide](PLUGIN_GUIDE.md)
- [API Reference](API.md)
- [Security Boundaries](SECURITY.md)
- [Extending CAPT](EXTENDING.md)
