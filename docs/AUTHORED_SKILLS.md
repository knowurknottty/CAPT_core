# CAPT Authored Skills

CAPT supports pinned external **authored skills** as governed model context.
They are prompt/context guidance, not executable Skill Foundry procedures and
not a capability, policy, proof, claim, or authority source.

## Canonical pack

The first pinned pack is `knowurknottty/CAPT_Skills` release `v0.1.0`.
CAPT ships an immutable lock at:

`capt_runtime/skill_packs/CAPT_Skills.lock.json`

The lock binds repository, release ref, commit, tree, and SHA-256 for every
`SKILL.md`. CAPT rejects the checkout if origin, HEAD/tree, cleanliness, path
safety, frontmatter identity/version, or content digest fails verification.

## Operator inspection

```zsh
capt skills status --root /path/to/CAPT_Skills
capt skills list --root /path/to/CAPT_Skills
capt skills show inversion-creative-director --root /path/to/CAPT_Skills
```

These commands are read-only and verify the packaged lock before returning
content or provenance.

## Governed model use

A governed model-operator command may explicitly select authored skills:

```json
{
  "objective": "Review the supplied interface evidence.",
  "targetRoot": "/path/to/target",
  "skillPackRoot": "/path/to/CAPT_Skills",
  "skillNames": ["inversion-interface-craft"]
}
```

CAPT parses and verifies the selection before mission/task/grant/lease mutation.
`DriverHost.prepare_authored_skills()` then freezes the exact verified bytes in
memory. Context construction uses that snapshot rather than re-reading disk,
closing the preflight-to-dispatch TOCTOU window.

The selected material enters the external runtime only through the validated
`ContextSlice.skillContext`. Hermes does not discover `~/.hermes/skills` or any
other ambient skill directory. The prompt labels authored skills as external,
context-only guidance that cannot grant tools, permissions, authority, or a
policy override.

Successful receipts expose provenance only: pack/version, repository/ref,
commit/tree, manifest digest, and selected skill/version/content digests. Skill
instruction bodies are not echoed into the authoritative receipt.

## Updating the pin

A new CAPT_Skills release is a supply-chain change, not an ambient update.
Publish and stamp the skill-pack release first, then update the CAPT lock to the
new immutable commit/tree/digests and run the authored-skill, contract, full
runtime, package, and installed-artifact gates.

Do not point CAPT at a moving branch, silently trust local edits, auto-publish
these documents into Skill Foundry, or let a driver discover them directly from
disk. Promotion of executable/procedural knowledge remains a separate governed
Foundry lifecycle.
