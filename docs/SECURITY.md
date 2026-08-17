# CAPT Core Security Boundaries

CAPT is local-first and fail-closed where its current contracts require it, but the repository does **not** equate local execution with high-assurance security.

## Threat model

The current public runtime primarily assumes one trusted local OS user. The host OS, account, filesystem, Python/Node runtimes, and any local model/provider processes are part of the trusted computing base unless separately isolated.

CAPT does not currently claim protection from a compromised host/account or full multi-user authorization.

## Existing controls

- authenticated local RuntimeService socket/token access;
- explicit capability/lease/governance boundaries;
- ordered EventStore history and integrity checks;
- idempotency/checkpoint/recovery controls;
- bounded DriverHost execution boundaries;
- secret references rather than raw provider tokens in operator provider config where supported;
- provider diagnostic/evidence secret scrubbing;
- imported package/Knowledge Bubble validation and quarantine controls;
- evidence/verification/ClaimGuard separation;
- conservative indeterminate-execution recovery in the active #46 lifecycle lineage.

## Active security gate — PR #49

PR #49 converts the pre-launch security checklist into executable fail-closed infrastructure. The correct current verdict is **BLOCKED** while applicable controls still lack exact-head evidence.

A security gate may evaluate and emit evidence. It does not grant capability or make itself authoritative.

## Known open controls / limitations

Current public CAPT does not claim comprehensive:

- CAPT-managed encryption at rest for persistent runtime/memory/evidence state;
- cryptographically signed independently rooted audit history;
- multi-user/tenant authorization;
- bounded production IPC framing on every path;
- rejection-event auditing across every invalid external request path;
- hardened file-permission enforcement for every artifact/state file;
- provider-wide request/output/token/cost/time ceilings;
- universal process/container isolation for external tools/models;
- adversarial prompt/context/provider-injection assurance;
- cryptographic Knowledge Bubble signature verification;
- exactly-once semantics for arbitrary external side effects.

## External execution

Driver output is untrusted until admitted through evidence/verification boundaries. A timeout/cancel request does not imply the external process or HTTP request was physically aborted unless the adapter proves that fact.

For indeterminate external dispatch, the safe recovery path is to mark/reconcile rather than automatically replay.

## Provider secrets

Do not persist raw API keys in memory, evidence, diagnostics, or prompt payloads. Prefer environment/keychain-backed references where the operator layer supports them.

Remote/cloud provider selection should be visibly distinguished from local inference.

## Hermes workspace metadata boundary

Operator-supplied LOCAL-002 metadata described `HERMES_LOCAL_002_COMPLETE`, successful non-destructive workspace suites, and no product/state-map blocker while leaving destructive external-provider/tool-kill rollback unproven. Terra could not retrieve `evidence/hermes-local-002-r6`, `5c8cbf5ec1dfc0034ba7fa0931e21c88fe0cfc04`, or the named report from the current GitHub remote/API, so those LOCAL-002 security/recovery statements are **currently unverified and must not close any control**.

The destructive rollback/reconciliation gate remains open independently of whether LOCAL-002 is later restored.

## Data at rest

Until CAPT-managed encryption is implemented and proven, rely on appropriate host full-disk/filesystem protection and restrictive local permissions for sensitive deployments.

## Verification

Security claims should be tied to exact source/evidence identities. A green general test suite does not automatically close a security control whose adversarial or destructive acceptance case has not run.

## Vulnerability reporting

Do not publish real secrets or sensitive CAPT data in a public issue. Use a private maintainer/security channel where available.

See [`CURRENT_STATE.md`](CURRENT_STATE.md) for the current integration/security status.