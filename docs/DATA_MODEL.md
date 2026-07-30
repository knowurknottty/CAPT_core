# CAPT Core Data Model

This document describes the persistent state used by the current CAPT Solo
reference implementation of CAPT Core.

All runtime state is local by default under `~/.capt-solo`.

## Storage layout

```text
~/.capt-solo/
├── data/
│   ├── memory.db
│   ├── ctp/
│   │   ├── journal.log
│   │   └── state.json
│   └── khsb/
└── backups/
```

## Memory database

### `memories`

| Column | Type | Notes |
|---|---|---|
| `memory_id` | TEXT PK | UUID4 hex identifier. |
| `content` | TEXT NOT NULL | Stored text content. |
| `namespace` | TEXT NOT NULL | Logical partition. |
| `provenance` | TEXT NOT NULL | Origin of the memory. |
| `confidence` | REAL NOT NULL | Range `0.0..1.0`. |
| `metadata` | TEXT NOT NULL | JSON object. |
| `created_at` | REAL NOT NULL | Unix epoch seconds. |
| `updated_at` | REAL NOT NULL | Unix epoch seconds. |

Indexes: `idx_mem_namespace`, `idx_mem_updated`.

### `tags`

| Column | Type | Notes |
|---|---|---|
| `memory_id` | TEXT NOT NULL | FK to `memories`, cascade delete. |
| `tag` | TEXT NOT NULL | Tag value. |

Primary key: `(memory_id, tag)`.

### `schema_version`

| Column | Type | Notes |
|---|---|---|
| `version` | INTEGER PK | Current schema version. |

The v0.4 schema version is `4`.

## Proof model

### `proof_evidence`

Stores evidence used to support capability, skill, and workflow claims.

| Column | Type | Notes |
|---|---|---|
| `evidence_id` | TEXT PK | UUID4 hex. |
| `type` | TEXT NOT NULL | Example: `test_pass`, `static_analysis`, `integration`. |
| `producer` | TEXT NOT NULL | Evidence producer. |
| `hash` | TEXT NOT NULL | SHA-256 of the evidence payload. |
| `trust` | REAL NOT NULL | Range `0.0..1.0`. |
| `provenance` | TEXT | Source or execution context. |
| `scope` | TEXT NOT NULL | Capability or workflow scope. |
| `created_at` | REAL NOT NULL | Unix epoch. |

### `proof_requirements`

Defines the evidence required for a scope to become proven or verified.

| Column | Type | Notes |
|---|---|---|
| `scope` | TEXT NOT NULL | Capability or workflow scope. |
| `type` | TEXT NOT NULL | Required evidence type. |
| `min_count` | INTEGER NOT NULL | Minimum evidence count. |
| `min_trust` | REAL NOT NULL | Minimum trust threshold. |

Primary key: `(scope, type)`.

## Capability model

### `capabilities`

| Column | Type | Notes |
|---|---|---|
| `capability_id` | TEXT PK | Example: `capt_solo.memory.store`. |
| `name` | TEXT NOT NULL | Human-readable name. |
| `namespace` | TEXT NOT NULL | Owning namespace. |
| `lifecycle_state` | TEXT NOT NULL | Candidate, validated, proven, verified, degraded, deprecated, revoked, or experimental. |
| `trust` | REAL NOT NULL | Aggregated trust value. |
| `creation_metadata` | TEXT | JSON metadata. |
| `ctp_refs` | TEXT | JSON array of linked CTP receipts. |
| `degradation_state` | TEXT | Current degradation state when applicable. |

### `capability_degradations`

Preserves why, where, and how a capability degraded.

| Column | Type | Notes |
|---|---|---|
| `capability` | TEXT NOT NULL | FK to `capabilities`. |
| `reason` | TEXT NOT NULL | One of the defined degradation reason codes. |
| `explanation` | TEXT | Human-readable explanation. |
| `affected_scope` | TEXT | Example: `macos` or `global`. |
| `triggering_evidence` | TEXT | Evidence that triggered the transition. |
| `previous_state` | TEXT | Prior lifecycle state. |
| `resulting_state` | TEXT | Degraded or revoked state. |
| `timestamp` | REAL NOT NULL | Unix epoch. |
| `actor` | TEXT | Named actor. |
| `remediation` | TEXT | Recovery guidance. |
| `ctp_tx_id` | TEXT | Linked CTP receipt when consequential. |

## Skill model

### `skills`

| Column | Type | Notes |
|---|---|---|
| `skill_id` | TEXT PK | UUID4 hex. |
| `name` | TEXT NOT NULL | Skill name. |
| `version` | TEXT NOT NULL | Semantic version. |
| `lifecycle_state` | TEXT NOT NULL | Candidate, generated, validating, validated, reviewing, approved, published, deprecated, or revoked. |
| `source_procedure` | TEXT | Originating procedure ID. |
| `content_hash` | TEXT | Deterministic substantive-content hash. |
| `ctp_refs` | TEXT | JSON array of linked CTP receipts. |
| `created_at` | REAL NOT NULL | Unix epoch. |
| `updated_at` | REAL NOT NULL | Unix epoch. |

## Workflow proof model

### `workflow_proofs`

A workflow carries independent proof rather than inheriting trust from individual
components.

| Column | Type | Notes |
|---|---|---|
| `workflow_id` | TEXT PK | Workflow identifier. |
| `workflow_version` | TEXT NOT NULL | Version string. |
| `lifecycle_state` | TEXT NOT NULL | Candidate, validated, proven, approved, verified, degraded, deprecated, or revoked. |
| `definition` | TEXT | JSON covering components, proof refs, I/O compatibility, dependency graph, permission union, escalation, environment compatibility, transaction boundary, rollback compatibility, evidence, and lifecycle metadata. |
| `ctp_tx_id` | TEXT | CTP receipt for consequential transitions. |
| `created_at` | REAL NOT NULL | Unix epoch. |

## Governance model

### `governance_audit`

| Column | Type | Notes |
|---|---|---|
| `audit_id` | TEXT PK | Audit identifier. |
| `action` | TEXT NOT NULL | Example: `publish_skill`, `deprecate_capability`. |
| `actor` | TEXT NOT NULL | Named actor; anonymous governance is rejected. |
| `target` | TEXT | Affected object ID. |
| `ctp_tx_id` | TEXT | Linked CTP receipt. |
| `reason` | TEXT | Human-readable reason. |
| `timestamp` | REAL NOT NULL | Unix epoch. |

## Knowledge Bubble model

### `knowledge_bubbles`

| Column | Type | Notes |
|---|---|---|
| `bubble_id` | TEXT PK | Bubble identifier. |
| `name` | TEXT NOT NULL | Bubble name. |
| `lifecycle_state` | TEXT NOT NULL | Imported, quarantined, validated, approved, or installed. |
| `definition` | TEXT | Full v2 manifest. |
| `content_hash` | TEXT | Manifest hash. |
| `validation_report` | TEXT | JSON report from the 12-step validation. |
| `imported_at` | REAL | Import time. |
| `installed_at` | REAL | Install time. |
| `approved_by` | TEXT | Named approving actor. |
| `ctp_tx_id` | TEXT | CTP receipt for installation. |

## Cognitive Transaction Protocol journal

`ctp/journal.log` is append-only JSON Lines in event order.

```json
{"type":"begin","tx_id":"...","correlation_id":"c1","idempotency_key":"k1","meta":{},"ts":123.0}
{"type":"validate","tx_id":"...","checks":{"ok":true},"result":true,"ts":123.1}
{"type":"commit","tx_id":"...","idempotency_key":"k1","ts":123.2}
```

Supported event types are `begin`, `validate`, `commit`, `abort`, and `note`.
A transaction is finalized only when a `commit` or `abort` event exists.
`recover()` reports transactions with no finalizing event.

## Export format

Memory exports are portable, human-readable JSON.

```json
{
  "format": "capt-solo-memory",
  "version": 1,
  "exported_at": 123.0,
  "memories": []
}
```

## Human inspectability

- Inspect the database with `sqlite3 ~/.capt-solo/data/memory.db`.
- Exports are indented, diff-friendly JSON.
- CTP journals are plain JSON Lines.
- Lifecycle, proof, degradation, and governance state remain explicitly stored
  rather than inferred from transient model output.

## Migration safety

Forward schema migrations are backup-gated. A verified SQLite backup and integrity
check must succeed before a migration is applied. Failure aborts the migration and
prevents partial schema state.
