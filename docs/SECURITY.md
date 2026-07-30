# CAPT Core Security Boundaries

CAPT Core is local-first by design. This document describes the protections
implemented by the current CAPT Solo reference runtime, the trust assumptions it
makes, and the controls it does **not** yet provide.

## Security goals

The current runtime is designed to:

- avoid mandatory cloud services and network egress
- minimize secret handling
- keep persistent state local and inspectable
- preserve transaction integrity and crash recovery
- prevent unsupported capability claims
- quarantine imported governed packages before approval
- attribute consequential actions to named actors
- fail closed on unsafe migrations and validation failures

## Trust model

CAPT Solo currently assumes a single trusted local user and operating-system
account. It is not a multi-user authorization service.

The host operating system, filesystem permissions, Python runtime, and local
account are part of the trusted computing base.

## Architectural protections

- **No required network egress.** The base runtime performs no telemetry, update
  check, or remote database call.
- **No external database.** Persistent state is stored in local SQLite files under
  `~/.capt-solo`.
- **No Docker requirement.** The runtime does not depend on a privileged container.
- **No required API secrets.** Core operation does not require model-provider keys.
- **Stable public boundary.** Public callers use `capt_solo.api`; raw SQL is kept
  out of the public API and CLI surfaces.

## Data at rest

Memory, exports, backups, and transaction journals are plaintext unless protected
by external filesystem or disk encryption.

Do not store credentials, access tokens, private keys, or unnecessary sensitive
personal data in CAPT memory content or metadata.

On multi-user systems, restrict the runtime directory appropriately, for example:

```bash
chmod 700 ~/.capt-solo
```

## Integrity and recovery

- SQLite integrity is checked with `PRAGMA integrity_check` and referential checks.
- CTP journals are append-only and flushed per write.
- `recover()` identifies transactions without a final commit or abort event.
- Reusing a finalized idempotency key raises an error instead of applying the same
  operation twice.
- Forward migrations require a verified backup, integrity check, and receipt.
- Failed backup or integrity validation aborts the migration before partial apply.

## Proof and claim controls

- A capability, skill, or workflow is not reported verified without sufficient
  evidence for its declared requirements.
- ClaimGuard downgrades unsupported or stale claims.
- Degradation is scope-aware so a platform-specific failure is not represented as
  a global revoke.
- Capability lifecycle transitions and degradation records preserve provenance and
  remediation context.

## Skill and package validation

- Skill validation uses a 12-stage harness.
- Unsafe command patterns, secret patterns, and disallowed permissions fail
  validation.
- A rollback strategy is required before a skill can be validated.
- Imported Knowledge Bubbles are quarantined by default.
- Bubble validation is manifest-first and blocks unsafe permissions and secret
  patterns before approval.
- Imported bubbles are not automatically trusted, executed, or installed.

## Governance audit

Consequential actions such as approval, publication, installation, deprecation,
and revocation are:

- executed inside CTP transaction boundaries
- attributed to a named actor
- linked to append-only audit records
- rejected when anonymous governance is attempted

## Component isolation and secret minimization

Optional components are expected to degrade independently rather than becoming a
mandatory failure point for the core runtime.

The hardened Anti-Token-Extraction integration is designed to run locally over a
bounded stdio JSON-RPC boundary with cache mode disabled, sensitive-input refusal,
and no credentials passed through MCP arguments.

## Known limitations

The current runtime does **not** claim:

- encryption at rest
- multi-user authentication or authorization
- cryptographic verification of Knowledge Bubble signatures
- cryptographically signed CTP audit trails
- protection from a compromised host operating system or local account
- universal isolation for every optional external model or tool runtime

These limitations are intentional documentation, not implied future functionality.
Consumers requiring a higher-trust environment must add appropriate host,
filesystem, identity, isolation, and cryptographic controls.

## Security validation

The repository includes automated tests, runtime verification, diagnostics, and
release validation. Security-related changes should include a reproducer or
regression test whenever practical.

Run:

```bash
./verify.sh
./doctor.sh
python verify_runtime.py
python -m pytest tests/ -q
```

## Reporting vulnerabilities

Report security issues privately to the maintainer before public disclosure. Do
not open public issues containing real secrets or data from a local CAPT store.

## Planned higher-trust work

Reserved future work includes:

- encrypted backup and export
- cryptographic Knowledge Bubble verification
- signed CTP receipts and audit records
- optional authenticated remote stores behind the stable API
- stronger process isolation for optional components
