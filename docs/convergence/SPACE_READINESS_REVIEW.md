# SPACE_READINESS_REVIEW

Generated: 2026-07-30. Audit target: integration HEAD `716ecc9` (and public
main for cross-check). Question: is the Treasure Chest `Space` (doc 15
Workstream D) already present under another name, partial, or absent?

## 1. Search results — every isolation/governance concept in the codebase

| Concept | Location | What it actually is | Space-equivalent? |
|---|---|---|---|
| `namespace` (memory) | `capt_solo/memory/interfaces.py` (MemoryRecord.namespace), `csg.py` (retrieval weight), `engram.py`, `deduplicate.py` | Per-record string label; partitions retrieval scoring and dedup; no policy, no lifecycle, no ACL | Seam only — a Space could map to a namespace set |
| `ProjectWorkspace` / `WorkspaceScope` / `BindState` / `ProjectContext` | `capt_solo/evidence/workspace_isolation.py` | Evidence-subsystem project isolation: binds evidence records to a project scope, isolation-violation errors | Closest existing boundary, but evidence-only |
| `workspace.py` (repo workspace) | `capt_solo/workspace.py` | The AGENTS.md workspace contract: CURRENT_STATE/CHECKPOINT validation, task queue, bootstrap. Repository-operations tool, not runtime isolation | NOT a Space; different meaning of "workspace" |
| Foundry `bubble` export | `capt_solo/foundry/bubble.py` (`exported_namespaces`) | Export/import container for skills/procedures with namespace selection | Precedent for Space export/import semantics |
| Sessions | `capt_solo/lifecycle/sessions.py` | Session lifecycle below the would-be Space boundary | Object a Space would govern, not the boundary |
| CTP journal | `capt_solo/ctp/journal.py` | `journal_dir` per runtime instance; no scope field in receipts | Space would add a scope ref to transactions |
| Capability registry / governance | foundry | Capability states + approvals, global (single-tenant) | Space would partition these |

Verdict per mission vocabulary: **genuinely absent as a first-class concept;
represented only by reserved seams and one subsystem-local isolation
implementation.** Not "distributed across subsystems" in any coordinated way —
the seams do not reference each other.

## 2. Current-state model (implicit)

CAPT Solo today is single-tenant-per-state-directory. Isolation boundary =
the state directory (`.capt_state/` / configured paths). Within it: memory
namespaces (flat labels), evidence project scopes (typed), everything else
global. There is exactly one implicit "space" and it has no identity record.

## 3. Intended Space model (doc 15 D, condensed)

Durable identity + lifecycle + members + memory namespaces + capability
policy + tool permissions + runtime bindings + CTP scope + evidence scope +
governance history + import/export + recovery + audit. Ten operations,
isolation guarantees, deterministic default-Space migration, no orphans.

## 4. Gap analysis

| Space element | Existing seam | Gap size |
|---|---|---|
| Identity/metadata/lifecycle | none | New table + model (small) |
| Memory namespace ownership | namespace strings exist | Mapping table + enforcement in engine calls (medium) |
| Evidence scope | ProjectWorkspace exists | Adapt: project scope becomes Space-owned (medium) |
| Capability/tool policy | global registry | Partition + policy checks (large) |
| Runtime/model bindings | nothing (no adapters) | BLOCKED on TC-RUNTIME (Workstream E) |
| CTP transaction scope | no scope field | Additive receipt field + journal partitioning (medium; schema change) |
| Governance/audit history | global | Space-scoped views (medium) |
| Export/import | bubble precedent | Extend bubble pattern to Space bundle (medium) |
| Default-Space migration | n/a | One-time migration: adopt all existing state into `space:default` (medium, MUST be backup-gated) |

## 5. Migration implications

- Schema: memory DB (schema v5) gains space mapping; CTP receipts gain scope
  ref. Both are ADDITIVE if designed as nullable-with-default → existing rows
  adopt `space:default` deterministically. Orphan risk concentrates in: skills,
  bubbles, capability records, evidence links — each needs an adoption rule.
- Backward compatibility: public API additive (new `capt_solo.spaces` module +
  optional space parameter on existing entry points defaulting to the default
  Space). Existing callers unaffected. I-08 (migration path) applies.
- STOP CONDITION per mission: if implementation would CHANGE existing stable
  API signatures (rather than extend), owner direction required first.

## 6. Proposals (design-only; no code)

- Package: `capt_solo/spaces/` (model.py, store.py, policy.py, migrate.py).
- API surface: `SpaceManager.create/get/list/update/activate/deactivate/
  export/import_/archive/tombstone`; `Space` dataclass with schema_version.
- Persistence: new SQLite tables `spaces`, `space_members`,
  `space_namespace_map`, `space_policy`; receipts gain nullable `space_id`.
- Stability tier at introduction: **Provisional** (not Stable) for one minor
  version — public stability recommendation.
- Est. size: components comparable to the evidence subsystem (13 files);
  realistic risk: MEDIUM-HIGH (touches memory, CTP, foundry, governance).

## 7. Recommendation

Do NOT design a second overlapping abstraction: evolve `ProjectWorkspace`
into the evidence-scope view of a Space rather than replacing it. Implement
Spaces in v0.5.1/v0.6 (per V0_5_SCOPE_RECONCILIATION §4), with the migration
design reviewed against a copy of real user state before any migration runs.
Space work before adapter work (D before E) since E's policy selection
depends on Space policy — but E's CONTRACT can be drafted in parallel.
