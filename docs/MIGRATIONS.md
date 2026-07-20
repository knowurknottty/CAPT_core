# CAPT Solo v0.4 — Migrations

CAPT Solo uses forward-only, backup-gated SQLite migrations. The schema version
is stored in the `schema_version` table. The current version is
`SCHEMA_VERSION = 4`.

## Migration safety gate

Before ANY forward migration, `MemoryEngine._backup_before_migration(from_version)`
runs. This is a SAFETY GATE, not best-effort:

1. Opens a SEPARATE read connection to the canonical `self._db_path` (avoids
   WAL/transaction deadlock on the engine's own connection).
2. Uses SQLite's online `backup()` API to copy committed pages into
   `<home>/backups/capt_solo.v{from_version}.{timestamp}.db`.
3. Opens the backup and runs `PRAGMA integrity_check`; the backup must pass.
4. Records a receipt (source version, target version, backup path, timestamp,
   integrity_check result, success/error) to `<home>/backups/migration_receipt.json`.
5. If the backup or integrity check fails, raises `MigrationBackupError` and
   ABORTS the migration. The database is left untouched at the prior version.
6. `ALLOW_MIGRATION_WITHOUT_BACKUP = False` (default). Setting it True is a
   dev-only override that emits a severe warning and skips the gate. It must
   never be used in production.

## v0.4 migration (3 -> 4)

`_migrate` applies the v3->v4 step via `_create_v4()`, which adds: composite
workflows, workflow_proofs, governance_audit, capability_degradations, and
other v0.4 tables. The migration is idempotent: re-opening an already-v4
database performs no backup and no re-application.

## In-memory databases

CAPT Solo is always persistent (`memory_db_path()` returns a real filesystem
path). There is no true in-memory mode. A `:memory:` path is explicitly
rejected for migration (no backup possible); the engine raises and the caller
must use a real path.

## Implemented

- Backup-gated forward migration (safety gate, not best-effort).
- Online `backup()` API + integrity_check + receipt.
- Abort-on-failure (no partial apply).
- Idempotent re-open (no duplicate backup, no re-apply).
- WAL-safe (separate source connection).

## Experimental

- None.

## Future

- Down-migration / rollback scripts (currently migrations are forward-only;
  rollback is via the backup file + manual restore).

## Limitations

- Migrations are forward-only; there is no automated down-migration.
- Backup is a file copy; very large databases may take time (acceptable).

## Security Boundaries

- Migration never proceeds without a verified backup (default config).
- The backup directory is created under the runtime home; it is never placed
  in a world-writable location by default.
- No migration writes to the source DB before the backup succeeds.

## Verification

- `tests/test_v04_migration.py` (8 tests: fresh->v4, idempotent, v3->v4,
  backup valid+integrity, backup filename uniqueness, abort-on-failure,
  in-memory explicit, v4 functional).
- `verify_runtime.py` (schema_version, migration_backup_dir).
- `doctor.sh` (schema version is 4, backup dir present).
