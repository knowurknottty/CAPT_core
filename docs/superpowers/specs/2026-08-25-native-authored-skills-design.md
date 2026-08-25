# CAPT Native Authored Skills R1 Design

## Goal

Give CAPT's governed model-operator path a managed local skill pack that can be imported from heterogeneous Agent Skills sources, contextually selected from the user's objective, frozen into the existing `ContextSlice.skillContext`, and surfaced to both native macOS editions without creating a second skill runtime.

## Existing authority

Current `main` already supports explicit pinned authored-skill context. It verifies a skill pack, freezes selected skill text before authoritative mutation, binds the exact model-visible prompt to approval, injects skill context through `DriverHost`, and records provenance-only receipts. The new work extends that spine; it does not replace it.

## State layout

Each CAPT runtime home owns its installed pack:

```text
<CAPT_STATE_DIR>/skills/ultimate/
  manifest.json
  skills/<skill-name>/SKILL.md
  skills/<skill-name>/...supporting files...
```

Standard native CAPT therefore resolves `~/.capt/skills/ultimate`; the Inversion Labs edition resolves `~/.capt-inversion-labs/skills/ultimate` when launched with that state directory.

## Import contract

`capt skills import --source <dir> --name ultimate --state-dir <root>` recursively accepts:

- directories containing valid `SKILL.md` files;
- flat Markdown skill files with YAML frontmatter (`name`, `description`);
- `.skill` ZIP bundles containing one or more skill directories.

The importer preserves each whole skill directory so references/scripts/assets remain available. It rejects archive path traversal, symlink escapes, invalid skill names, duplicate names with conflicting content, and files outside the imported skill directory. Identical duplicates collapse to one canonical installed skill and record all source origins.

Skills without a usable `name` + `description` frontmatter are not executable authored skills. Pack/index Markdown such as a root catalog is reported as skipped rather than silently converted into authority.

## Managed manifest

`manifest.json` is generated atomically and includes schema version, pack name/version, imported timestamp, source roots, and per-skill name, description, version, relative path, `SKILL.md` digest, directory-tree digest, trigger terms, and source origins. Verification recomputes every digest before context construction. Any post-import mutation fails closed until re-imported.

## Contextual selection

Selection is deterministic and bounded. Explicit `skillNames` remains highest authority. Otherwise, when `autoSelectSkills` is true or a managed default pack is present, CAPT ranks skills from:

1. exact/phrase matches in declared `triggers`/`trigger` frontmatter;
2. skill-name token matches;
3. description token/phrase matches;
4. `When to use` / `When to Apply` heading text;
5. title/heading tokens as a lower-weight fallback.

Stop words and very short tokens are ignored. Negative applicability phrases (`not for`, `skip for`, `do not use for`) reduce score when their terms match the objective. Selection is capped (default 4, hard max 8) and requires a minimum score; no-match returns zero skills rather than injecting generic context.

Selection itself grants no capabilities. Skills remain context-only guidance and cannot override CAPT policy, approvals, tool leases, filesystem/network boundaries, evidence rules, or release authority.

## Runtime integration

`request_model_prompt_approval` resolves the managed default pack from the ledger's state directory before prompt assembly. Selected names and frozen context are included in the exact approval binding. `run_approved_hermes` reuses only that prepared snapshot; it never re-ranks or re-reads mutable skill files after approval.

The existing explicit pinned external pack path remains supported for immutable released packs.

## Native macOS integration

The Swift client remains a renderer. It does not parse skills or rank prompts. Approval results expose selected authored skill names; `CAPTPendingApproval` stores them and Chat/Inspector surfaces show the names so the operator can see what will influence the model before approval.

## Installation target

After implementation, import `/Users/knowurknot/Desktop/Ultimate-skills` into both:

- `/Users/knowurknot/.capt/skills/ultimate`
- `/Users/knowurknot/.capt-inversion-labs/skills/ultimate`

Then verify identical manifest digests and contextual selection in each runtime home.

## Verification gates

- importer tests: directories, flat Markdown, `.skill` bundles, duplicates, traversal, tamper;
- selector tests: explicit override, relevant trigger, multi-skill composition, collision ordering, no-match, negative applicability;
- RuntimeService tests: selection occurs before approval and is bound to the prepared execution snapshot;
- Swift tests: pending approval decodes and preserves selected skill names;
- focused Python authored-skill suite green;
- full Python suite green;
- Swift suite green;
- installed-pack verification for both runtime homes;
- live smoke using representative objectives for CAPT engineering and web design.
