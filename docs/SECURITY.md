# CAPT Core Security Boundaries

CAPT is local-first and fail-closed where its contracts require it, but local execution is not automatically high-assurance security.

Snapshot date: **2026-08-27**.

## Threat model

The current public Core primarily assumes one trusted local OS user. The host OS/account, filesystem, language runtimes, container/SSH endpoints, and local model/provider processes are part of the trusted computing base unless separately isolated. CAPT does not claim protection from a compromised host/account or full multi-user authorization.

## Integrated controls on merged `main`

Current `main` includes:

- authenticated local RuntimeService socket/token access;
- bounded production JSON framing and malformed/oversized-frame rejection;
- capability/lease/governance boundaries and governed revoke;
- ordered EventStore history and integrity checks;
- covered security-rejection auditing;
- restrictive permissions for covered runtime state files;
- request/token/cost resource ceilings at governed provider admission;
- prompt/context/provider injection-assurance regressions;
- durable idempotency/checkpoint/recovery and indeterminate-dispatch handling;
- exact model-visible human-approval binding and one-use consumption;
- provider secret references/scrubbing rather than raw-secret evidence persistence;
- authenticated encryption for covered sensitive EventStore/MemoryStore content and encrypted native session-cache storage;
- evidence/verification/ClaimGuard/task-completion separation;
- the 47-control Security Closure Cockpit;
- governed ToolBroker/ToolExecution lifecycle and reconciliation for bounded external tools;
- authored-skill provenance, exact approval binding, and execution-time anti-drift checks.

These implementation facts do **not** automatically mark corresponding release controls PASS. SecurityGate requires the evidence class specified for each exact source identity.

## Tool execution security boundary

PR #126 added governed ToolBroker support for local, SSH, and Docker terminal backends plus file/code adapters without moving authority into adapters.

Important constraints:

- readiness is not effect proof;
- a requested cancellation does not prove an external process or side effect stopped;
- consequential execution remains capability/lease governed;
- durable ToolExecution state records dispatch/effect/settlement boundaries;
- unknown external effect state becomes reconciliation-required rather than a blind retry;
- SSH/Docker profiles and remote/container trust remain part of the deployment threat model.

ToolBroker is not a sandbox guarantee. Stronger process/container isolation remains a separate assurance class.

## Authored-skill security boundary

PR #129 adds `managed_local` authored-skill packs alongside existing `pinned_external` packs.

Skills are non-authoritative context. They cannot grant filesystem/network/tool capability, provider credentials, approvals, verification, or policy overrides.

Selected skill identity/content is bound before approval and revalidated before dispatch. Changed approved bytes fail closed. Oversized skills above the current inline contract are not silently truncated.

## CI gate integrity

The `Release Security` workflow is intended to be a real release-authority gate rather than a decorative badge. It checks out the exact source, runs its security/regression/build/install checks, evaluates the Security Closure Cockpit evidence, uploads the gate artifacts, and fails when required evidence is not authorized.

The M0-A workflow similarly remains an engineering gate, not a release declaration.

## SHA-bound release-security history

Security authorization is bound to the exact source SHA evaluated.

- Historical merged PR #117 head `570babeef113943860c1268722200a48639e406d` remains **Release Security FAIL** on run `32440329043`.
- Release-security closure baseline `2199c036aa22af33fb3eb0700f63f820a35aa55a` passed hosted run `32617740908` with **21 PASS / 0 FAIL / 0 NOT_VERIFIED / 26 NOT_APPLICABLE** and no blockers. M0-A run `32617740848` also passed on that SHA.
- ToolBroker PR #126 exact head `b21ed6e7ff3996d48c756e342b278b69af0d666f` passed hosted M0-A and Release Security before squash merge. The squash merge `bcfdff9d43b35b5b192cc998b68ce16cc73b9985` is tree-identical but a different commit SHA; the PR-head receipt is not relabeled.
- At audit start, literal `main` `3aee7370bac880aed99ce3c9ecfaa6d9ff48101e` had an M0-A push run where Python 3.12, contract drift, and TypeScript parity passed but Python 3.10 failed because a Docker availability probe timed out during test collection. The failed job was retried during this audit.

Do not call `3aee737…` release-authorized merely because it descends from an authorized source. A later SHA needs its own evidence.

For a public artifact release, rebuild and hash the wheel/sdist/native artifacts from the exact authorized source, then complete any required signing, notarization, and distribution proof.

## Data at rest

Covered sensitive EventStore JSON payload/state/receipt/checkpoint/security-detail fields and MemoryStore content use authenticated encryption. Legacy plaintext rows are migrated on open, and wrong keys or modified ciphertext fail closed.

On macOS, the runtime state key is stored in Keychain when available. CI/tests may provide an explicit key; other supported hosts can use a user-private key file. SQLite DB/WAL/SHM files are owner-private, but CAPT does not chmod caller-owned pre-existing parent directories.

This is field-level protection for covered persisted content, not whole-disk encryption. Some metadata, digests, identifiers, and non-SQLite artifacts remain outside that encrypted-content boundary. Host full-disk/filesystem protection is still relevant.

## Provider secrets and remote execution

Do not persist raw API keys in prompts, evidence, diagnostics, or durable config. Prefer environment/keychain-backed references. Remote/cloud provider selection must remain visibly distinguishable from local inference, and every paid provider admitted to a release profile needs its own billing-cap/alert evidence where required.

## Remaining assurance boundaries

A green exact-source gate does **not** imply:

- protection from a compromised OS account/host;
- comprehensive multi-user/tenant authorization;
- universal process/container isolation;
- exactly-once arbitrary external side effects;
- model correctness or prompt-safety guarantees;
- signed/notarized/distributed native release proof.

## Vulnerability reporting

Do not publish real secrets or sensitive CAPT data in a public issue. Use a private maintainer/security channel where available.

See [`CURRENT_STATE.md`](CURRENT_STATE.md) and [`RELEASE_EVIDENCE.md`](RELEASE_EVIDENCE.md) for the current source/evidence boundary.
