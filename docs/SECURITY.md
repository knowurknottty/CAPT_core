# CAPT Solo v0.5 — Security Model

CAPT Solo is local-first, not magically secure. This document states the
implemented boundaries and the trust that remains with the local user and host.

## Network boundary

- Core imports, Evidence, Verification, ContextPack, CTP, Workspace, Memory,
  KHSB, and Foundry require no network.
- The experimental PULSE gateway is disabled by default. It imports and uses its
  network client only after explicit configuration and invocation.
- CAPT has no telemetry or update check.

Local-first means the default runtime has no network requirement or hidden
egress. It does not mean an explicitly configured optional gateway is incapable
of network access.

## Data at rest

- Memory is plaintext SQLite under `CAPT_SOLO_HOME`.
- CTP and verification records are plaintext JSONL.
- Exports, backups, evidence, ContextPacks, and tutorial artifacts are
  plaintext.
- Runtime directories and CTP journals are created with restrictive POSIX
  permissions where supported, but the host filesystem and user account remain
  trust boundaries.

Do not place credentials, private keys, tokens, or unnecessary personal data in
CAPT records. Encryption at rest is not implemented.

## Integrity and recovery

- Memory uses SQLite integrity checks and referential-integrity checks.
- Forward schema migration is backup-gated unless a developer explicitly
  enables the documented unsafe override.
- CTP is append-only, flushes writes, records idempotency keys, and can identify
  pending transactions after restart.
- VSI ties verification applicability to repository, file, dependency,
  command, runtime, environment, and scope state.
- ContextPack v1 uses canonical serialization and digests.

Append-only does not mean cryptographically immutable. CTP journals and audit
records are not signed in v0.5 and a user with filesystem access can alter them.

## Untrusted content

- Imported bubbles remain untrusted until validation and approval.
- Skill validation rejects declared unsafe commands, secret patterns, and
  disallowed permissions.
- Workspace task, checkpoint, evidence, Markdown, JSON, YAML, and tool output are
  data; repository text cannot grant itself authority or capabilities.
- Capability boundaries default-deny actions not explicitly allowed.

Pattern screening is defense in depth, not a complete malware sandbox. Users
must inspect third-party code before executing it.

## Authentication and authorization

CAPT Solo is a local single-user runtime. It does not provide multi-user
authentication, remote authorization, tenant isolation, or a hardened service
perimeter. Do not expose the runtime directly as a network service without an
independent security design.

## Release verification

Release security evidence is candidate-specific. The current bounded report is
`docs/security/RELEASE_SECURITY_REPORT_V0.5.md`; historical v0.4 reports do not
prove a v0.5 candidate.

Run:

```bash
capt --json doctor
capt --json release validate
python3 verify_runtime.py
```

These checks do not replace a repository security scan or dependency audit.

## Reporting

Report suspected vulnerabilities privately to the maintainer. Do not include
real local-store data, credentials, or private evidence in public issues.
