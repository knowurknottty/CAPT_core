# CAPT Solo v0.1 — Data Model

All persistent state lives under `~/.capt-solo`.

```
~/.capt-solo/
├── data/
│   ├── memory.db            # SQLite: memories + tags
│   ├── ctp/
│   │   ├── journal.log      # append-only transaction journal (JSON lines)
│   │   └── state.json       # reserved for runtime state (currently unused)
│   └── khsb/                # reserved for future KHSB persistence
└── backups/                 # backup_*.db, memory_export_*.json
```

## `memory.db` schema

### `memories`
| Column | Type | Notes |
|--------|------|-------|
| `memory_id` | TEXT PK | UUID4 hex. |
| `content` | TEXT NOT NULL | The stored text. |
| `namespace` | TEXT NOT NULL DEFAULT 'default' | Logical partition. |
| `provenance` | TEXT NOT NULL DEFAULT 'unknown' | Where it came from. |
| `confidence` | REAL NOT NULL DEFAULT 1.0 | `0.0..1.0`. |
| `metadata` | TEXT NOT NULL DEFAULT '{}' | JSON object. |
| `created_at` | REAL NOT NULL | Unix epoch seconds. |
| `updated_at` | REAL NOT NULL | Unix epoch seconds. |

Indexes: `idx_mem_namespace`, `idx_mem_updated`.

### `tags`
| Column | Type | Notes |
|--------|------|-------|
| `memory_id` | TEXT NOT NULL | FK → `memories`, cascade delete. |
| `tag` | TEXT NOT NULL | |

Primary key: `(memory_id, tag)`. Index: `idx_tags_tag`.

### `schema_version`
| Column | Type | Notes |
|--------|------|-------|
| `version` | INTEGER PK | Current schema version (v0.4 = 4). |

## v0.4 — Foundry tables (`memory.db`)

### `proof_evidence`
| Column | Type | Notes |
|--------|------|-------|
| `evidence_id` | TEXT PK | UUID4 hex. |
| `type` | TEXT NOT NULL | e.g. `test_pass`, `static_analysis`, `integration`. |
| `producer` | TEXT NOT NULL | Who produced it. |
| `hash` | TEXT NOT NULL | sha256 of the evidence payload. |
| `trust` | REAL NOT NULL | `0.0..1.0`. |
| `provenance` | TEXT | Source/context. |
| `scope` | TEXT NOT NULL | Capability or workflow scope. |
| `created_at` | REAL NOT NULL | Unix epoch. |

### `proof_requirements`
| Column | Type | Notes |
|--------|------|-------|
| `scope` | TEXT NOT NULL | Capability/workflow scope. |
| `type` | TEXT NOT NULL | Required evidence type. |
| `min_count` | INTEGER NOT NULL | Minimum evidence count. |
| `min_trust` | REAL NOT NULL | Minimum trust threshold. |

Primary key: `(scope, type)`.

### `capabilities`
| Column | Type | Notes |
|--------|------|-------|
| `capability_id` | TEXT PK | e.g. `capt_solo.memory.store`. |
| `name` | TEXT NOT NULL | Human label. |
| `namespace` | TEXT NOT NULL | Owning namespace. |
| `lifecycle_state` | TEXT NOT NULL | candidate/validated/proven/verified/deprecated/revoked/degraded/experimental. |
| `trust` | REAL NOT NULL | Aggregate trust. |
| `creation_metadata` | TEXT | JSON. |
| `ctp_refs` | TEXT | JSON array of CTP receipt ids. |
| `degradation_state` | TEXT | Set when degraded. |

### `capability_degradations`
| Column | Type | Notes |
|--------|------|-------|
| `capability` | TEXT NOT NULL | FK → capabilities. |
| `reason` | TEXT NOT NULL | One of 12 DEGRADATION_REASONS codes. |
| `explanation` | TEXT | Human-readable. |
| `affected_scope` | TEXT | e.g. `macos`, `global`. |
| `triggering_evidence` | TEXT | Evidence id that triggered. |
| `previous_state` | TEXT | Lifecycle before degradation. |
| `resulting_state` | TEXT | Lifecycle after (degraded/revoked). |
| `timestamp` | REAL NOT NULL | Unix epoch. |
| `actor` | TEXT | Who degraded. |
| `remediation` | TEXT | Guidance. |
| `ctp_tx_id` | TEXT | CTP receipt if consequential. |

### `skills`
| Column | Type | Notes |
|--------|------|-------|
| `skill_id` | TEXT PK | UUID4 hex. |
| `name` | TEXT NOT NULL | |
| `version` | TEXT NOT NULL | Semantic version. |
| `lifecycle_state` | TEXT NOT NULL | candidate/generated/validating/validated/reviewing/approved/published/deprecated/revoked. |
| `source_procedure` | TEXT | Procedure id. |
| `content_hash` | TEXT | Deterministic hash of substantive content. |
| `ctp_refs` | TEXT | JSON array of CTP receipt ids. |
| `created_at` / `updated_at` | REAL NOT NULL | |

### `workflow_proofs`
| Column | Type | Notes |
|--------|------|-------|
| `workflow_id` | TEXT PK | |
| `workflow_version` | TEXT NOT NULL | |
| `lifecycle_state` | TEXT NOT NULL | candidate/validated/proven/approved/verified/degraded/deprecated/revoked. |
| `definition` | TEXT | JSON: components, proof refs, io compat, dep graph, permission union, escalation, env compat, tx boundary, rollback compat, evidence, lifecycle metadata. |
| `ctp_tx_id` | TEXT | CTP receipt for consequential transitions. |
| `created_at` | REAL NOT NULL | |

### `governance_audit`
| Column | Type | Notes |
|--------|------|-------|
| `audit_id` | TEXT PK | |
| `action` | TEXT NOT NULL | e.g. `publish_skill`, `deprecate_capability`. |
| `actor` | TEXT NOT NULL | Named actor (never anonymous). |
| `target` | TEXT | Affected id. |
| `ctp_tx_id` | TEXT | Linked CTP receipt. |
| `reason` | TEXT | |
| `timestamp` | REAL NOT NULL | |

### `knowledge_bubbles`
| Column | Type | Notes |
|--------|------|-------|
| `bubble_id` | TEXT PK | |
| `name` | TEXT NOT NULL | |
| `lifecycle_state` | TEXT NOT NULL | imported/quarantined/validated/approved/installed. |
| `definition` | TEXT | Full bubble manifest (v2). |
| `content_hash` | TEXT | Hash of manifest. |
| `validation_report` | TEXT | JSON of 12-step validation. |
| `imported_at` / `installed_at` | REAL | |
| `approved_by` | TEXT | Actor who approved. |
| `ctp_tx_id` | TEXT | CTP receipt for install. |

## `ctp/journal.log`

One JSON object per line, append-only, in event order:

```json
{"type":"begin","tx_id":"...","correlation_id":"c1","idempotency_key":"k1","meta":{},"ts":123.0}
{"type":"validate","tx_id":"...","checks":{"ok":true},"result":true,"ts":123.1}
{"type":"commit","tx_id":"...","idempotency_key":"k1","ts":123.2}
```

Event types: `begin`, `validate`, `commit`, `abort`, `note`.
A transaction is **finalized** when a `commit` or `abort` event exists for its
`tx_id`. `recover()` returns tx ids with no finalizing event.

## Export format (`memory_export_*.json`)

```json
{
  "format": "capt-solo-memory",
  "version": 1,
  "exported_at": 123.0,
  "memories": [ { ...Memory.to_dict() fields... } ]
}
```

## Human-readability

- `memory.db` can be inspected with `sqlite3 ~/.capt-solo/data/memory.db`.
- Exports are indented JSON, diff-friendly, and portable between machines.
