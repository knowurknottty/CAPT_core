# CAPT Solo v0.1 — Security

CAPT Solo is **local-first by design**. This document states what that means for
security and where the boundaries are.

## What is protected by architecture

- **No network egress.** The runtime makes zero outbound connections. KHSB is
  in-process only. There is no telemetry, no update check, no remote call.
- **No external database.** All state is a local SQLite file under
  `~/.capt-solo`. No credentials, no connection strings.
- **No Docker / container.** Nothing runs in a privileged container.
- **No secrets required.** The runtime needs no API keys to operate.

## Data at rest

- Memory is stored in plaintext SQLite. **Do not store secrets, tokens, PII, or
  credentials in memory content or metadata.** Export files (`export_json`) and
  backups are also plaintext.
- File permissions follow the user's umask. On multi-user machines, restrict
  `~/.capt-solo` with `chmod 700` if sensitive project memory is stored.

## Integrity

- Memory integrity is verified via SQLite `PRAGMA integrity_check` plus a
  tag-referential-integrity cross-check (`MemoryEngine.integrity_check()`).
- CTP journals are append-only and flushed on every write. A crash cannot
  corrupt committed history; `recover()` replays and reports pending txns.
- `idempotency_key` in CTP prevents double-application of an operation. Reusing
  a finalized key raises `IdempotencyError`.

## v0.4 — Additional security boundaries

- **Migration safety gate.** Forward migrations are backup-gated. Before any
  schema bump, a verified `sqlite3.backup()` + `integrity_check` is taken.
  Failure aborts the migration (no partial apply). `ALLOW_MIGRATION_WITHOUT_BACKUP`
  is `False` by default; enabling it is a dev-only override that emits a severe
  warning.
- **ClaimGuard downgrade.** No capability/skill is reported verified without a
  satisfied proof aggregate. Degraded/revoked capabilities are always downgraded.
  Scoped degradation language prevents a platform-specific issue (e.g. macOS)
  from being misreported as a global revoke.
- **Bubble quarantine.** Imported bubbles are never trusted, executed, or
  auto-installed. Validation runs 12 checks (manifest before payload) before
  approval. Secret patterns and unsafe permissions block validation.
- **Skill validation.** The 12-stage harness rejects unsafe command patterns
  (`rm -rf`, `sudo`, `format`), secret patterns, and disallowed permissions.
  A skill without a rollback strategy (>=10 chars) cannot be validated.
- **Governance audit.** All consequential actions (publish, deprecate, revoke,
  approve, install) run inside a CTP transaction with a named actor and an
  append-only audit trail. Anonymous governance is rejected.
- **Public surface is SQL-free.** `api.py` and `capt_cli.py` contain no raw SQL;
  the plugin exposes only stable public tools (`public_only: true`).

## What is NOT a security feature (v0.4)

- **No encryption at rest.** (unchanged from v0.1)
- **No authentication/authorization.** (unchanged; local single-user trust)
- **Bubble signatures are placeholder.** `signature_metadata` exists but no
  cryptographic verification is performed in v0.4.
- **No audit signing.** CTP audit trails are append-only, not cryptographically
  signed (reserved for v1.0).

## Reporting

CAPT Solo is intended for open-source release. Report security issues privately
to the maintainer before public disclosure. Do not open public issues containing
real data from your local store.

## Future (reserved, not implemented)

- Encrypted backup/export (`--encrypt`).
- Optional GPG-signed CTP receipts.
- Remote memory stores with auth (behind the same public API).
