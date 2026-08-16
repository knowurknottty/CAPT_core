# CAPT Core Security Closure R1

Status: **BLOCKED — source review complete enough to identify current release blockers; exact-head execution evidence still required**

Source-review anchor: `406260915b4a8264c4c7525e9fd6f910d4a068e9`
Profile: `security/profiles/capt-core.json`
Control set: 40 operator-supplied screenshot controls + 6 CAPT supplemental controls
Applicable to current local-first Core profile: 20

This document is a source-backed closure ledger, not a PASS certificate. A control marked `IMPLEMENTED_EVIDENCE_PENDING` has a credible implementation/control path but still requires exact-head execution or verifier evidence. `PARTIAL` and `GAP` remain release-blocking.

## R1 classification

| Control | R1 state | Source-backed reason | Required closure evidence/action |
|---|---|---|---|
| VIBE1-01 Hide API keys | IMPLEMENTED_EVIDENCE_PENDING | Provider configuration stores secret references, resolves env/keychain material only at call time, and provides deep scrubbing/redaction helpers; cognitive provenance records `credentialMaterial: not_recorded`. | Exact-head secret-boundary tests + secret scan. |
| VIBE1-02 Purge Git secrets | EVIDENCE_PRODUCER_READY | Release workflow performs a full-history gitleaks action. | Successful exact-head gitleaks run; CI emits ephemeral attestation. |
| VIBE1-05 Encrypt sensitive data | GAP | EventStore and MemoryStore use ordinary SQLite; memory content and mission/task/event JSON may be sensitive and are not encrypted by CAPT at rest. Sensitivity metadata is not encryption. | Choose and implement an at-rest encryption/key-management contract; do not invent custom cryptography. |
| VIBE1-06 Enforce server-side auth | IMPLEMENTED_EVIDENCE_PENDING | Runtime IPC authenticates the first frame with a per-start random token stored 0600 and binds operator/session identity server-side. Model dispatch additionally requires a runtime-owned approved prompt-assembly receipt. | Exact-head auth, forged identity, approval-receipt and stale/edit invalidation tests. |
| VIBE1-07 Lock record access | PARTIAL | Runtime clients reach records through authenticated local IPC, but the SQLite files themselves do not yet enforce explicit CAPT-owned filesystem modes and an authenticated operator can query arbitrary known stream IDs. | Harden on-disk permissions; explicitly define single-user record authorization semantics and test denied paths. |
| VIBE1-08 Block field tampering | IMPLEMENTED_EVIDENCE_PENDING | Authoritative writes validate generated contracts; command identity is connection-bound; operation fingerprints/idempotency reject conflicting reuse; event payload digests are computed by the store rather than accepted from callers. | Exact-head contract/forged-command/idempotency tests. |
| VIBE1-13 Parameterize queries | IMPLEMENTED_EVIDENCE_PENDING | Reviewed EventStore read/write paths use SQLite placeholders for attacker-influenced values; MemoryStore insertion is parameterized. | Dedicated injection-regression tests at exact head across all SQLite stores. |
| VIBE1-14 Validate all input | PARTIAL | Authoritative state transitions use generated contracts and bounded enums, but the local IPC query surface does not yet have a single schema/size-validation boundary for every request. | Add bounded frame validation plus typed request schemas/validation for all IPC operations. |
| VIBE1-17 Trim API responses | PARTIAL | Cognitive provenance excludes credential material and provider observations truncate summary text, but general `get_state`/event queries can return complete authoritative records to the authenticated local operator. | Define projection/minimization contract per IPC operation; prove secrets/private fields cannot cross unnecessarily. |
| VIBE1-20 Scan dependencies | EVIDENCE_PRODUCER_READY | Release workflow runs `pip-audit` over installed dependency closure. | Successful exact-head pip-audit; CI emits ephemeral attestation. |
| VIBE2-09 Block prompt injection | PARTIAL | CAPT structurally prevents prompt/model text from granting capabilities or authoritative state, and provider observations are untrusted. The Core prompt surface does not claim a universal lexical injection detector, and adversarial context/instruction-boundary tests are not yet a complete release gate. | Define control as prevention of authority/policy override by untrusted prompt/context; add adversarial tests over context, memory, provider and retrieved content. |
| VIBE2-10 Cap AI usage | PARTIAL | Capability leases enforce allowed operations, time scope and requested `maxSeconds`; provider transport has a 120-second timeout. No complete token/cost/output/request-count ceiling is enforced across provider calls. | Add governed token/cost/request/output budgets and lease accounting; test exhaustion and replay. |
| VIBE2-11 Limit request size | GAP | Current desktop IPC `_recv_json` trusts its 32-bit peer-supplied frame length and reads until that size; no hard maximum is enforced. `capt_runtime.ipc_framing` now defines a bounded transport helper, but the production desktop service has not yet been migrated to it. | Migrate authoritative IPC server/client to bounded framing and add oversized/truncated/partial-header tests. |
| VIBE2-13 Sanitize before storing | PARTIAL | Contracts validate structured authoritative data and secret helpers redact credentials in UI/diagnostics. Evidence/event systems intentionally preserve source truth, so destructive generic sanitization would be incorrect. Memory content and free text still need explicit secret/control-character/unsafe-content policy. | Define per-field normalize/validate/redact/preserve rules; never mutate evidentiary source text silently. |
| VIBE2-18 Log security events | GAP | EventStore durably records accepted authoritative transitions, but many rejected auth/authority/contract attempts return errors without a dedicated durable security-event taxonomy. | Add non-secret security audit events for auth failure, authorization denial, malformed/oversize IPC, stale approval, capability denial, and security-gate decisions. |
| VIBE2-20 Restrict database permissions | GAP | SQLite paths are created/opened without explicit CAPT chmod enforcement for DB/WAL/SHM/memory-policy files. Host umask is currently relied upon. | Enforce/verify owner-only file modes on runtime-owned persistence and test sidecar files. |
| CAPT-SUP-01 Authorize every mutation at authoritative boundary | IMPLEMENTED_EVIDENCE_PENDING | `authority.py` is deny-by-default by authoritative act; `RuntimeService` is the cross-aggregate mutation path and calls `require_authority`. | Exact-head authority-negative suite and operation-surface inventory. |
| CAPT-SUP-04 Minimize privileged/debug data crossing into clients | IMPLEMENTED_EVIDENCE_PENDING | Secret resolution remains server-side; provenance records digests/references rather than credentials; scrubbers exist for diagnostics. | Exact-head projection/redaction tests including exception paths. |
| CAPT-SUP-05 Test denied-access cases | IMPLEMENTED_EVIDENCE_PENDING | Existing tests include unauthenticated IPC, forged command identity, authority/capability denials and other fail-closed cases. | Execute mapped negative suite at exact release head and emit evidence refs. |
| CAPT-SUP-06 Treat AI/security-sensitive output as untrusted until verified | IMPLEMENTED_EVIDENCE_PENDING | Provider driver observations explicitly carry `trust: untrusted`; CAPT verification separately constructs authoritative Evidence/Verification and ClaimGuard rejects unproven completion/security claims. | Exact-head provider→evidence→verification→claim discrimination tests. |

## Confirmed architectural strengths

The R1 review found several controls already embedded in the architecture rather than bolted on:

- authority is deny-by-default by act and actor kind;
- authoritative mutation is centralized through RuntimeService/store transactions;
- SQL reviewed in EventStore is parameterized;
- event payload digests are computed inside the store and hash-chained;
- provider keys use references/keychain/environment resolution rather than raw configuration persistence;
- provider/model observations are explicitly untrusted;
- verification and ClaimGuard are separate from driver completion;
- capability leases constrain identity, task/mission scope, operation class, resource path, lifetime and a time budget;
- release CI already has gitleaks and pip-audit evidence producers.

These are source observations. They become release PASS evidence only after exact-head verification under the security gate.

## Confirmed blockers requiring implementation

### B1 — at-rest sensitive-data protection

Do not solve this with homemade crypto. CAPT needs a deliberate encryption/key-management choice for local persistence, including memory content, event/aggregate state where sensitive fields may occur, backups/checkpoints, key rotation/recovery, and what remains intentionally plaintext for recovery. Platform-backed key wrapping or a vetted encrypted SQLite strategy should be evaluated before implementation.

### B2 — bounded IPC framing and complete input validation

A peer-controlled length prefix must be bounded before body allocation/read. The new `capt_runtime.ipc_framing` helper provides the intended primitive (`MAX_FRAME_BYTES`, exact partial reads, object-only JSON, malformed/truncated/oversize failures), but production IPC must actually use it before VIBE2-11 can pass.

### B3 — security-relevant rejection audit trail

Rejected actions are often exactly what an operator needs during incident review. CAPT should define a bounded security-audit event shape that records category, operation, actor/session correlation, reason code, source surface and timestamp while excluding credentials and unsafe raw payloads. It must not turn rejected input into authoritative domain success.

### B4 — runtime persistence permissions

CAPT-owned DB, WAL/SHM and related state files need explicit owner-only permissions, verified after creation and sidecar creation, rather than assuming a favorable umask.

### B5 — complete AI resource governance

Current leases/timeouts are useful but do not establish a total cost/token/request/output budget. AI usage controls should become lease-accounted resource dimensions, not UI counters.

### B6 — prompt/context injection assurance

CAPT's core safety objective is stronger than keyword blocking: untrusted text may influence cognition but must not alter authority, capabilities, tools, policy or acceptance state. Security closure therefore needs adversarial tests that inject hostile instructions through every untrusted content path and prove governance/tool/approval state is unchanged. Lexical detectors may be defense-in-depth, never the authority boundary.

## Evidence model correction

An earlier draft proposed committing exact-SHA PASS evidence to `security/profiles/capt-core-evidence.json`. That is self-invalidating: changing the evidence file creates a new commit SHA. The committed file is now only an empty fail-closed local baseline.

Release CI generates `security-evidence.json` *after checking out the exact source SHA and running checks*, using `capt_runtime.security_evidence`. The generated artifact is then consumed by `capt_runtime.security_gate` and uploaded alongside `security-gate-result.json`. This preserves exact-head provenance without a self-referential commit.

## Next closure order

1. Integrate bounded framing and DB/file-permission hardening because both are deterministic local changes.
2. Add a security-audit rejection event path without polluting successful domain-event semantics.
3. Specify and implement AI budget dimensions.
4. Design at-rest encryption with vetted primitives/key management; do not rush this control.
5. Build the adversarial prompt/context security suite.
6. Add per-control verifier adapters and map targeted tests/scanners into ephemeral evidence.
7. Run the complete exact-head closure; only then populate a PASS decision artifact.

Until that sequence (or an evidence-equivalent implementation) is complete, CAPT Core security status is **BLOCKED**, not "mostly secure" and not release-approved.
