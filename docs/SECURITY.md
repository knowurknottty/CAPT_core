# CAPT Core Security Boundaries

CAPT is local-first and fail-closed where its contracts require it, but local execution is not automatically high-assurance security.

## Threat model

The current public Core primarily assumes one trusted local OS user. The host OS/account, filesystem, language runtimes, and local model/provider processes are part of the trusted computing base unless separately isolated. CAPT does not currently claim protection from a compromised host/account or full multi-user authorization.

## Integrated security controls in the terminal convergence line

The convergence candidate incorporates the security infrastructure and UPG-001→019 hardening rather than leaving them as independent stale PRs. Implemented mechanisms include:

- authenticated local RuntimeService socket/token access;
- bounded production JSON framing and oversized/malformed-frame rejection;
- explicit capability/lease/governance boundaries and governed revoke;
- ordered EventStore history and integrity checks;
- durable security-rejection auditing for the covered invalid-authority paths;
- restrictive persistence permissions for covered runtime database/state files;
- request/token/cost resource ceilings at governed provider admission;
- prompt/context/provider injection-assurance regressions;
- durable idempotency/checkpoint/recovery and indeterminate-dispatch handling;
- exact model-visible human-approval binding, one-use consumption, and stale/mismatched rejection;
- provider secret references/scrubbing rather than evidence persistence of raw credentials;
- encrypted native session-cache storage with explicit private filesystem-permission tests;
- evidence/verification/ClaimGuard/task-completion separation;
- Security Closure Cockpit projection over a **47-control** catalog, including the explicit paid-service billing-cap/alert requirement.

These implementation/test facts do **not** automatically mark their corresponding release controls PASS. SecurityGate requires the evidence class specified for each exact-head control.

## Current release-security verdict

The terminal convergence classification remains:

`IMPLEMENTED_CROSS_SURFACE_VERIFIED_RELEASE_SECURITY_BLOCKED`

The latest terminal-candidate cockpit was **BLOCKED / releaseAuthorized=false** because applicable controls lacked legitimate exact-head closure evidence. A `NOT_VERIFIED` result means evidence is absent/stale/incomplete; it is not equivalent to a discovered vulnerability and must not be silently converted to PASS.

## Known substantive/open assurance areas

Current public Core still does not claim comprehensive:

- CAPT-managed encryption at rest for all sensitive authoritative runtime/memory/evidence state;
- independently rooted/signed audit-history attestations;
- multi-user/tenant authorization;
- universal process/container isolation for external tools/models;
- exactly-once semantics for arbitrary external side effects;
- release evidence for paid-service billing caps/alerts across every applicable external service;
- final signed/notarized native application distribution security.

Other controls may remain `NOT_VERIFIED` even where implementation exists until exact-head evidence is produced.

## External execution

Driver output is untrusted until admitted through evidence/verification boundaries. A timeout/cancel request does not prove an external process or HTTP request was physically aborted unless the adapter proves it. If dispatch state is indeterminate, CAPT suspends/reconciles rather than blindly replaying consequential work.

## Provider secrets and remote execution

Do not persist raw API keys in memory, evidence, diagnostics, or prompt payloads. Prefer environment/keychain-backed references. Remote/cloud provider selection must remain visibly distinguishable from local inference, and remote billing/resource controls require their own closure evidence.

## Data at rest

The native session cache has encrypted storage and private-permission regression coverage. That fact must **not** be generalized into a claim that all authoritative EventStore/memory/evidence state is CAPT-encrypted at rest.

Until the applicable authoritative-state encryption controls are implemented and proven, sensitive deployments should also rely on appropriate host full-disk/filesystem protection and restrictive local permissions.

## Verification rule

Security claims are tied to exact source/evidence identities. General Python/Swift suites, sanitizer passes, and cross-surface acceptance support engineering correctness; they do not independently authorize release-security controls whose required evidence has not been supplied.

## Vulnerability reporting

Do not publish real secrets or sensitive CAPT data in a public issue. Use a private maintainer/security channel where available.

See [`CURRENT_STATE.md`](CURRENT_STATE.md) and [`RELEASE_EVIDENCE.md`](RELEASE_EVIDENCE.md) for current integration and evidence status.
