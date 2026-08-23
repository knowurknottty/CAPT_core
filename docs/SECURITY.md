# CAPT Core Security Boundaries

CAPT is local-first and fail-closed where its contracts require it, but local execution is not automatically high-assurance security.

## Threat model

The current public Core primarily assumes one trusted local OS user. The host OS/account, filesystem, language runtimes, and local model/provider processes are part of the trusted computing base unless separately isolated. CAPT does not currently claim protection from a compromised host/account or full multi-user authorization.

## Integrated security controls on merged `main`

Merged `main` incorporates the security infrastructure and UPG-001→019 hardening rather than leaving them as independent stale PRs. Implemented mechanisms include:

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

## CI gate integrity

The terminal convergence work corrected a material CI-authority mismatch: the inherited workflow named `Release Security` did not actually execute the Security Closure Cockpit. It could therefore report workflow success while CAPT's release gate remained blocked.

The workflow now:

1. checks out the exact pull-request head;
2. runs Python security/regression/build/install/invariant/dependency-audit checks;
3. runs full-history gitleaks;
4. verifies SecurityGate/evidence machinery;
5. generates ephemeral exact-head attestations from checks that really passed;
6. evaluates the 47-control CAPT Core profile;
7. uploads `security-evidence.json` and `security-gate-result.json`;
8. fails the workflow if the exact-head gate is not authorized.

A red `Release Security` workflow is therefore now an intentional release-authority signal when required evidence is incomplete, not a generic test badge.

## Release-security authority and closure status

Release-security authorization is bound to the exact source SHA being evaluated. The historical merged PR #117 head `570babeef113943860c1268722200a48639e406d` remains a **failed** Release Security receipt (run `32440329043`); later work does not rewrite that history.

The security-closure implementation supplies explicit proof for all **21 applicable** controls in the 47-control Core profile. Its local projection is **21 PASS / 0 FAIL / 0 NOT_VERIFIED / 26 NOT_APPLICABLE**. The hosted `Release Security` workflow must reproduce PASS on the exact source SHA before that SHA is release-security authorized.

The closure proof classes include:

- full-history secret scanning and dependency closure audit;
- named Python tests for authentication, authorization, parameterized queries, input bounds, output minimization, injection resistance, resource ceilings, denied-access paths, audit events, and AI-output verification;
- AES-256-GCM authenticated encryption of sensitive file-backed EventStore JSON fields and MemoryStore content, with legacy plaintext migration, wrong-key/tamper startup rejection, and private DB/sidecar permissions;
- a one-shot CAPT spend-threshold alert that contains cost/request counters only;
- a live OpenRouter inference-key policy query that rejects missing hard caps and refuses management/provisioning credentials in CI.

A green checklist decision does **not** imply protection from a compromised host account, comprehensive multi-user/tenant authorization, universal process/container isolation, exactly-once arbitrary external side effects, or signed/notarized native distribution. Those remain separate assurance/release classes. Any additional paid provider added to the release profile must provide its own provider-side hard cap plus independent alert evidence before release authorization can remain green.

## External execution

Driver output is untrusted until admitted through evidence/verification boundaries. A timeout/cancel request does not prove an external process or HTTP request was physically aborted unless the adapter proves it. If dispatch state is indeterminate, CAPT suspends/reconciles rather than blindly replaying consequential work.

## Provider secrets and remote execution

Do not persist raw API keys in memory, evidence, diagnostics, or prompt payloads. Prefer environment/keychain-backed references. Remote/cloud provider selection must remain visibly distinguishable from local inference, and remote billing/resource controls require their own closure evidence.

## Data at rest

The native session cache remains encrypted. Core file-backed runtime persistence now additionally protects sensitive EventStore JSON payload/state/receipt/checkpoint/security-detail fields and MemoryStore content with AES-256-GCM authenticated encryption. Legacy plaintext rows are migrated on open and the SQLite WAL is checkpointed before vacuuming; unexpected plaintext after migration, wrong keys, and modified ciphertext fail closed.

On macOS, the runtime state key is stored in Keychain when available. CI/tests may provide an explicit 32-byte base64 key; other supported hosts fall back to a user-private `~/.capt/keys/` key file (`0700` directory / `0600` key file). SQLite DB/WAL/SHM files are owner-private, but CAPT does not chmod caller-owned pre-existing parent directories.

This is field-level protection for sensitive persisted content, not whole-disk encryption. Indexing identifiers, schema metadata, digests, and some non-SQLite artifact files remain outside that encrypted content boundary. A compromised OS account/host remains outside the current threat claim and should still be mitigated with host full-disk/filesystem protection.

## Verification rule

Security claims are tied to exact source/evidence identities. General Python/Swift suites, sanitizer passes, and cross-surface acceptance support engineering correctness; they do not independently authorize release-security controls whose required evidence has not been supplied.

## Vulnerability reporting

Do not publish real secrets or sensitive CAPT data in a public issue. Use a private maintainer/security channel where available.

See [`CURRENT_STATE.md`](CURRENT_STATE.md) and [`RELEASE_EVIDENCE.md`](RELEASE_EVIDENCE.md) for current integration and evidence status.
