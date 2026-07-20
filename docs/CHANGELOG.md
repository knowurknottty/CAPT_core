# CAPT Solo — Changelog

## v0.4.1 (2026-07-20) — Anti-Token-Extraction Component Integration

### Added
- **Anti-Token-Extraction component** (`capt_solo/components/`): optional,
  independently degradable capability running as a local child process over
  stdio (JSON-RPC 2.0). Cache mode off, sensitive-input refusal on, no
  credentials in MCP arguments.
- **Pinned upstream manifest**: `UPSTREAM_REPO` + `PINNED_COMMIT`
  (https://github.com/knowurknottty/anti-token-extraction @ b68adac…) recorded
  in `ATEManifest`; `verify_pinned_commit()` confirms install matches.
- **Bundled offline stdio server** (`_ate_stdio_server.py`) mirroring the
  pinned upstream contract; replace with the pinned upstream build for prod.
- **Legacy cache purge** on bootstrap/upgrade (`purge_legacy_cache()`).
- **Hermes MCP template** (`anti_token_extraction.mcp.json`): stdio, cache off,
  refusal on, no creds, isolation metadata.
- **Capability registration**: `register_capability(reg)` registers
  `anti-token-extraction` as `candidate`, `optional`, `independently_degradable`.
- **Plugin tool**: `capt_anti_token_extraction_status` (47 tools total).
- **doctor.sh**: `v04.anti_token_extraction` check (pass healthy+pinned; warn
  absent/degraded — never blocks core).
- **verify_runtime.py**: 8 `component.ate_*` checks (warn-only).
- **Tests**: `tests/test_v04_anti_token_extraction.py` (9 scenarios: absent,
  healthy, wrong commit/version, MCP startup failure, unsafe cache, secret
  schema rejection, scoped degradation, bootstrap idempotency, legacy-cache purge).
- **Docs**: `docs/ANTI_TOKEN_EXTRACTION.md`.

### Changed
- `plugin.json` version 0.4.0 → 0.4.1; tool count 46 → 47.
- `install.sh`: bootstraps the component (idempotent) and purges legacy caches.
- `doctor.sh`: version label v0.4.1; plugin tool count 47.

### Safety
- Failure of this component degrades ONLY the anti-token-extraction capability
  (scoped `affected_scope`). Memory, CTP, KHSB, governance, ClaimGuard, plugin
  loading, and core runtime remain operational.

## v0.4.0 (2026-07-19) — Proof-Governed Cognitive Operating System

### Added
- **Skill Foundry**: procedure → skill candidate → evidence → 12-stage validation
  → review → publish. Full lifecycle with explicit transitions.
- **Proof Engine**: evidence objects + aggregation against declared requirements.
- **Capability Registry**: candidate→validated→proven→verified (3 distinct,
  idempotent events). 12 explicit degradation reason codes with structured records.
- **ClaimGuard**: claim validation with downgraded language; scoped degradation
  (macOS-only ≠ global revoke).
- **Knowledge Bubble Runtime**: v2 manifest (bubble_id, version, namespaces,
  artifact inventory, per-artifact hashes, manifest hash, signature placeholder,
  redaction declaration, declared permissions/dependencies, export policy,
  provenance) + 12-step validation (manifest before payload). Quarantine-by-default.
- **Governance Layer**: all consequential actions CTP-bounded + audited.
- **Workflow Proof Engine**: composed workflows carry independent proof; do NOT
  inherit component verification.
- **Migration safety gate**: backup-gated forward migration (sqlite3.backup() +
  integrity_check + receipt; abort on failure). `ALLOW_MIGRATION_WITHOUT_BACKUP=False`.
- **CLI**: `foundry` group (skills, capabilities, bubbles, governance, curate, audit).
- **Plugin**: 10 new v0.4 foundry tools (46 total).
- **Doctor/verify**: extended with v0.4 checks (schema v4, backup dir, foundry
  import, 12 degradation codes, CLI availability, plugin count, verify_runtime).
- **Boundary audit**: `api.py` + `capt_cli.py` confirmed SQL-free; regression test.

### Changed
- `SCHEMA_VERSION` 3 → 4 (v0.4 tables: composite_workflows, workflow_proofs,
  governance_audit, capability_degradations).
- `build_skill` rollback default is now `None` (empty string is respected as a
  real, validation-failing value).

### Schema
- Forward-only migrations. Backup taken before any version bump. Idempotent re-open.

### Verification
- 348 tests passing (migration, workflow proof, degradation, bubble, CLI, plugin,
  foundry, boundary, v0.1–v0.3 regression).
- `verify_runtime.py` exercises all subsystems end to end.
- `doctor.sh` reports v0.4 environment health.

## v0.3.0 — Lifecycle, Sessions, Procedures, Prospective Memory
## v0.2.0 — KHSB bus, CTP transactions, retrieval feedback
## v0.1.0 — Memory engine, core, plugin scaffold
