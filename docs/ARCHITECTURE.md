# CAPT Solo v0.1 — Architecture

CAPT Solo is the smallest stable public foundation of the CAPT cognitive runtime,
designed for **individual developers** who want a **local-first** memory and
transaction layer that integrates with Hermes. It is explicitly **not** the full
CAPT architecture.

## Design principles

| Principle | How it is satisfied |
|-----------|---------------------|
| Zero cloud dependency | No network calls anywhere in the runtime. |
| Zero external database | SQLite (Python stdlib) is the only store. |
| Zero Docker requirement | Pure Python; runs from a checkout. |
| Zero network requirement | KHSB is in-process only in v0.1. |
| One-command install | `./install.sh` |
| One-command health check | `./verify.sh` (or `capt_health`) |
| Portable between machines | All state under one directory (`~/.capt-solo`). |
| Deterministic behavior | No randomness in storage; UUIDs are for ids only. |
| Human-readable data | JSON export; SQLite `.dump` available. |
| Backward-compatible migrations | Versioned schema; `_migrate()` hook. |

## Component map

```
capt_solo/
├── core/          # config (paths), errors (public exception hierarchy)
├── memory/        # MemoryEngine (SQLite) + SearchAdapter interface
├── ctp/           # CTPRuntime (append-only journal)
├── khsb/          # KHSB in-process message bus
├── plugin/        # Hermes plugin — stable public tools only
├── skills/        # 8 beginner-friendly Hermes skills
└── api.py         # THE public surface (only sanctioned import path)
```

## Public surface vs implementation

The **only** module integrators should import is `capt_solo.api`. It re-exports
stable classes/functions and hides internals. Adding future capabilities
(vector search, distributed KHSB, federation, bioCAPT) means **adding** to this
surface — never changing existing names/signatures within a major version.

## Data flow

```
Hermes tool call
   → capt_solo.plugin.CaptSoloPlugin.<tool>   (thin wrapper)
   → capt_solo.api.<PublicClass>              (stable boundary)
   → implementation (memory/ctp/khsb)        (may change internally)
```

## Extension points (reserved, NOT implemented in v0.1)

1. **Vector search** — implement `SearchAdapter` and call
   `MemoryEngine.set_search_adapter(...)`. Public memory API unchanged.
2. **Distributed KHSB** — implement a `Transport` that routes
   `KHSB.publish/request` over a network. Public bus API unchanged.
3. **Remote memory stores** — swap `MemoryEngine`'s storage backend behind the
   same public methods.
4. **Multi-agent federation** — coordinate via CTP correlation ids across agents.
5. **bioCAPT integration** — consume `MemoryEngine` as a local memory sink.

None of these are present in v0.1. The seams exist; the implementations do not.

## Recovery model

CTP journals are **append-only and flushed on every write**. After any crash,
`CTPRuntime.recover()` replays the journal and returns any transaction left
pending (uncommitted/unaborted). Memory integrity is verified with SQLite's
`PRAGMA integrity_check` plus a tag referential-integrity cross-check.

## Thread safety

`MemoryEngine` relies on SQLite connection per instance (callers should use one
engine per thread or guard externally). `CTPRuntime` and `KHSB` use `RLock` to
serialize mutations safely within a process.

## v0.4 — Proof-Governed Cognitive Operating System

v0.4 adds four integrated subsystems on top of the v0.1–v0.3 foundation, all
local-first and zero-dependency (Python 3.9.6 stdlib only):

- **Skill Foundry** — procedure → skill candidate → evidence → validate (12-stage
  harness) → review → publish. Lifecycle: candidate→generated→validating→validated
  →reviewing→approved→published→deprecated→revoked. Approve ≠ publish.
- **Proof Engine** — evidence objects + aggregation against declared requirements.
  No capability/skill is reported verified without a satisfied aggregate.
- **Capability Registry** — single source of truth for "can CAPT do X?". Lifecycle
  candidate→validated→proven→verified (3 distinct, idempotent events). 12 explicit
  degradation reason codes with structured records.
- **ClaimGuard** — gates completion claims; downgrades unsupported claims; scoped
  degradation language (macOS-only degradation ≠ global revoke).
- **Knowledge Bubble Runtime** — portable, governed packages. Quarantine-by-default
  import; v2 manifest with 12-step validation (manifest before payload).
- **Governance Layer** — all consequential actions CTP-bounded + audited.
- **Workflow Proof Engine** — a composed workflow does NOT inherit component
  verification; it carries its own proof with independent lifecycle.

### v0.4 component map (additions)

```
capt_solo/foundry/
├── proof.py          # ProofEngine, Evidence, ProofAggregate
├── registry.py       # CapabilityRegistry, DEGRADATION_REASONS
├── claimguard.py     # ClaimGuard, ClaimVerdict
├── skill_foundry.py  # SkillFoundry, Skill
├── harness.py        # ValidationHarness (12 stages)
├── curator.py        # SkillCurator
├── composition.py    # CompositionEngine
├── workflow_proof.py # WorkflowProofEngine, WorkflowProof
├── bubble.py         # KnowledgeBubbleRuntime (v2 manifest)
└── governance.py     # Governance (CTP-bounded audit)
```

### v0.4 data flow

```
Hermes tool call
   → capt_solo.plugin.CaptSoloPlugin.<tool>   (thin wrapper, 46 tools)
   → capt_solo.api.<PublicClass>              (stable boundary)
   → capt_solo.foundry.<Subsystem>            (proof-governed)
   → capt_solo.memory.MemoryEngine            (SQLite, migration-gated)
```

### v0.4 migration safety gate

Forward migrations are backup-gated: before any schema bump, a verified
`sqlite3.backup()` of the canonical DB is taken + `integrity_check` passed +
receipt recorded. Failure aborts the migration (no partial apply).
`ALLOW_MIGRATION_WITHOUT_BACKUP=False` by default.
