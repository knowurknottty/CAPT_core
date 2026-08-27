# CAPT Authored Skills

CAPT supports authored skills as **governed model context**. They are prompt/guidance material, not executable Skill Foundry procedures and not a capability, policy, proof, claim, or authority source.

## Trust classes

Current `main` supports two explicit trust classes:

- **`pinned_external`** — an immutable externally maintained pack whose repository/ref/commit/tree/content digests are pinned by CAPT. `knowurknottty/CAPT_Skills` release `v0.1.0` is the canonical first example.
- **`managed_local`** — a local Agent Skills pack imported into the CAPT state root, normalized into a manifest, integrity-bound by digests, and reverified before governed use.

Trust class describes provenance. It does **not** elevate a skill into authority.

## Pinned external CAPT_Skills

CAPT ships the immutable lock:

`capt_runtime/skill_packs/CAPT_Skills.lock.json`

The lock binds repository, release ref, commit, tree, and SHA-256 for every selected `SKILL.md`. CAPT rejects the checkout if origin, HEAD/tree, cleanliness, path safety, frontmatter identity/version, or content digest fails verification.

Read-only inspection remains available:

```zsh
capt skills status --root /path/to/CAPT_Skills
capt skills list --root /path/to/CAPT_Skills
capt skills show inversion-creative-director --root /path/to/CAPT_Skills
```

## Managed local Agent Skills

PR #129 adds governed import and verification of heterogeneous local Agent Skills sources, including normal skill directories and supported `.skill` bundles.

Import a managed pack:

```zsh
capt skills import --source /path/to/skills
```

Verify the installed default pack:

```zsh
capt skills verify
```

Optional controls:

```zsh
capt skills import --source /path/to/skills --name ultimate --state-dir /path/to/capt-state
capt skills verify --name ultimate --state-dir /path/to/capt-state
```

Without `--state-dir`, the CLI uses the same canonical CAPT runtime state-root resolver as the runtime. The default managed pack name is `ultimate`.

Import copies/normalizes the accepted source into CAPT-managed state and records immutable manifest/content/tree digests. Later source-directory edits do not silently rewrite the installed pack.

## Selection precedence

A governed model request can explicitly select the pinned external pack:

```json
{
  "objective": "Review the supplied interface evidence.",
  "targetRoot": "/path/to/target",
  "skillPackRoot": "/path/to/CAPT_Skills",
  "skillNames": ["inversion-interface-craft"]
}
```

Explicit `skillPackRoot` / `skillNames` selection has higher precedence than managed-local contextual selection.

When there is no explicit selection, CAPT may select from the verified default managed pack using the request objective. Contextual auto-selection can be disabled with `autoSelectSkills: false`; `skillLimit` bounds the selected set and defaults to 4.

Selection is deterministic for the same verified pack and objective under the same implementation.

## Approval binding and anti-drift enforcement

The selected authored-skill context is resolved **before** model prompt approval. CAPT binds the skill names and `AuthoredSkillContext` provenance into the exact approval basis and validated `ContextSlice`.

Before dispatch, the runtime revalidates the selected managed pack/material. If the approved skill bytes or integrity identity drift, execution fails closed rather than silently substituting new instructions or consuming the approval for a different context.

Provider/Hermes projection receives the approved authored-skill material through the governed context path. Ambient discovery from `~/.hermes/skills`, arbitrary working directories, or other agent folders is not treated as CAPT authority.

Successful receipts expose provenance/digests rather than echoing the instruction bodies into authoritative evidence.

## Size boundary

The current inline authored-skill contract has a **32,768-character** per-skill ceiling. Oversized skills may remain installed and integrity-verified but are non-inlineable and fail closed; CAPT does not silently truncate them.

The verified Ultimate-skills import used during PR #129 contained four such oversized entries: `design-taste-frontend`, `immersive-brand-experience`, `last30days`, and `verify-before-claim`. File-backed governed loading for oversized skills is future work unless a later source change proves otherwise.

## Authority boundary

Authored skills cannot grant or widen:

- filesystem or network access;
- tool execution authority;
- provider credentials or billing authority;
- capabilities or leases;
- human approvals;
- verification/ClaimGuard status;
- RuntimeService/EventStore authority;
- security-policy overrides.

A skill can advise a model. CAPT decides what the model is allowed to do.

## Updating supply-chain inputs

A new `CAPT_Skills` release is a supply-chain change, not an ambient update. Publish/stamp the external pack first, update the CAPT lock to the new immutable commit/tree/digests, and run authored-skill, contract, full-runtime, package, and installed-artifact gates.

Managed-local packs likewise require an explicit import to change their governed snapshot. Do not treat a moving source folder as the installed truth.

Promotion of executable/procedural knowledge remains a separate governed Foundry lifecycle.
