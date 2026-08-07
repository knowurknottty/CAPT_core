# CAPT Core Security Boundaries

CAPT Core is local-first by design. This document describes the protections implemented by CAPT Solo and the v0.5 Runtime Harness, the assumptions they make, and the controls they do not yet provide.

## Trust model

The current release assumes one trusted local operating-system user and account. The host operating system, filesystem permissions, Python runtime, and local account are part of the trusted computing base.

CAPT Core is not currently a multi-user authorization service and does not defend against a compromised host account or process with equivalent filesystem access.

## Security goals

The current runtime is designed to:

- avoid mandatory cloud services and required network egress;
- minimize secret handling;
- keep persistent state local and inspectable;
- authenticate local harness access;
- preserve EventStore ordering, replay, and integrity evidence;
- preserve CTP transaction receipts and recovery state;
- reject duplicate or stale runtime operations where specified;
- prevent unsupported capability and completion claims;
- quarantine imported governed packages before approval;
- attribute consequential actions to named actors;
- fail closed on unsafe migrations and validation failures.

## Public security surfaces

### CAPT Solo API

`capt_solo.api` exposes supported in-process memory, CTP, KHSB, and proof-governed services. Raw SQL and internal runtime mutation are not public integration contracts.

### CAPT Runtime Harness

The installed `capt harness` surface communicates with an authenticated local RuntimeService. Runtime authority remains inside CAPT through EventStore, Memory Governor, ContextPack, TaskResolver, DriverHost, checkpointing, and recovery.

External clients such as Hermes are callers. They do not become the runtime or system of record.

## Data at rest

Memory, exports, backups, EventStore databases, and transaction journals are plaintext unless protected by host, filesystem, or disk encryption.

Do not store credentials, access tokens, private keys, or unnecessary sensitive personal data in CAPT memory or metadata.

Restrict local runtime directories to the trusted user, for example:

```zsh
chmod 700 ~/.capt-solo
```

## Integrity, replay, and recovery

- EventStore owns the authoritative ordered runtime event ledger.
- CTP records operational transaction receipts and recovery state; it is not the authoritative runtime ledger.
- SQLite integrity is checked with `PRAGMA integrity_check` and referential checks where applicable.
- Idempotency keys and command classifications prevent specified duplicate application paths.
- Checkpoints preserve restart state.
- Resume evidence demonstrates prior execution is not repeated in the proven lifecycle.
- Forward migrations require a verified backup, integrity check, and receipt.
- Failed backup or integrity validation aborts migration before partial application.

These controls do not create a universal exactly-once guarantee for arbitrary external side effects.

## Memory and context boundaries

The CAPT Solo Memory Engine stores persistent local knowledge.

The Runtime Memory Governor is a separate subsystem that owns trigger policy, token accounting, ContextPack rotation, stale-pack rejection, budget enforcement, and dispatch gating.

External drivers should receive only the authorized ContextPack slice or reference. They should not receive unrestricted durable-memory access.

## Proof and claim controls

- Capabilities, skills, and workflows require sufficient evidence for their declared requirements.
- ClaimGuard downgrades unsupported or stale claims.
- Degradation remains scope-aware.
- Verification evidence preserves process outcome, evidence identifiers, scope, environment, and limitations.
- Local real-process proof is not represented as hosted-CI proof.

## Skill and package validation

- Skill validation uses staged checks and proof requirements.
- Unsafe command patterns, secret patterns, disallowed permissions, and missing rollback strategies can block validation.
- Imported Knowledge Bubbles are quarantined by default.
- Bubble validation is manifest-first.
- Imported bubbles are not automatically trusted, executed, or installed.

## External drivers and providers

The base runtime requires no provider credential. Optional external drivers may require network access or credentials.

External model output is untrusted until processed through the governed evidence and verification path.

The currently proven Hermes-facing action is bounded read-only inspection. General unrestricted model-driven repository engineering is not claimed.

## Optional Anti-Token-Extraction integration

The optional Anti-Token-Extraction component is designed to run over a bounded local stdio JSON-RPC boundary with cache mode disabled, sensitive-input refusal, and no credentials passed through MCP arguments.

Hosted CI cannot currently verify the private optional dependency. Release Security therefore surfaces `DEGRADED_OPTIONAL_DEPENDENCY` rather than presenting a silent full-security pass.

## Known limitations

The current runtime does **not** claim:

- encryption at rest;
- multi-user authentication or authorization;
- cryptographic Knowledge Bubble signature verification;
- cryptographically signed EventStore or CTP records;
- protection from a compromised operating system or local account;
- universal isolation for every optional external model or tool runtime;
- unrestricted safe repository mutation by an external model.

Higher-trust environments must add suitable host, filesystem, identity, isolation, encryption, and cryptographic controls.

## Security validation

Run:

```zsh
./verify.sh
./doctor.sh
python3 verify_runtime.py
python3 -m pytest tests/ -q
```

The release evidence under [`release_evidence/v0.5`](../release_evidence/v0.5) records exact artifact, test, lifecycle, and limitation information.

## Reporting vulnerabilities

Report vulnerabilities privately before public disclosure. Do not open a public issue containing real secrets or data from a CAPT store.

A dedicated private vulnerability-reporting channel is still a documented near-term repository-hardening task. Until it is enabled, contact the repository maintainer through an established private channel.

## Planned higher-trust work

Future work may include encrypted backup/export, signed attestations and receipts, cryptographic Knowledge Bubble verification, stronger driver isolation, and separate multi-user authorization profiles.

These are planned directions, not current capability claims.
