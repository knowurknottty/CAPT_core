# CAPT Security Infrastructure Gate

Status: **implementation foundation — fail-closed release gate**
Branch: `feat/security-infrastructure-gate`
Initial stack base: `c42410d4b6f7d57444398a4032e258cbdf243c33`

## Intent

Security is a first-class CAPT infrastructure concern, not a checklist remembered at the end of a project.

This subsystem converts a pre-launch security checklist into a deterministic control catalog and exact-SHA evidence gate. The same catalog can be applied to CAPT Core and to future CAPT-managed applications through capability profiles.

The gate is intentionally non-authoritative. It does not create missions, claims, verification truth, capability grants, leases, or EventStore facts. Instead it evaluates evidence and exits non-zero when an applicable release control is failed or unverified. A future RuntimeService admission path may persist the resulting assessment as evidence/verification, but this module does not invent that authority.

## Sources

The source catalog preserves all 40 controls visible in the two operator-supplied pre-launch screenshots (20 + 20). The operator also supplied this reference:

`https://app.notion.com/p/The-Complete-Pre-Launch-Security-Checklist-for-Vibe-Coded-Apps-3b7512560bf28158a7a9e80ce3849e1e?source=copy_link`

The review environment could not directly fetch the Notion body. The 40 visible controls are therefore the exact source baseline in this implementation. Six CAPT supplemental controls cover mutation-boundary authorization, private storage, auth-token rejection, client data minimization, denied-access tests, and treating AI/security-sensitive output as untrusted. If the Notion page contains additional unique controls, they should be added as new stable IDs rather than silently changing the meaning of an existing ID.

## Core invariants

1. **No silent green.** Missing evidence for an applicable control is `NOT_VERIFIED`, and blocks release.
2. **Evidence is source-bound.** PASS/FAIL evidence must name the exact source SHA. PASS evidence from an ancestor is downgraded to `NOT_VERIFIED`.
3. **N/A is structural.** A control becomes not-applicable only because the declared application profile does not expose that capability surface.
4. **No checklist bypass state.** v1 has no `WAIVED` status. Accepted-risk exceptions, if ever added, must be a separate governed CAPT decision with owner, scope, expiry, evidence, and audit trail.
5. **Security evidence is not authority.** A scanner result does not itself become a capability grant, claim acceptance, task completion, or mission completion.
6. **All source controls remain visible.** Overlapping items such as HTTPS, HSTS, headers, upload restriction, and upload-type whitelisting remain separate controls because they prove different properties.
7. **Profiles are additive.** When CAPT gains a web, payment, upload, public API, browser, or password-auth surface, those controls automatically become applicable instead of relying on a human to remember to add them.

## Data model

`capt_runtime/security_gate.py` contains:

- `SecurityControl`: stable control identity, category, severity, applicability capabilities, and verification hint.
- `SecurityProfile`: application exposure/capability profile.
- `SecurityEvidence`: exact-SHA PASS/FAIL/NOT_VERIFIED evidence with verifier and references.
- `evaluate_security_gate(...)`: pure deterministic evaluation.
- `SecurityGateResult`: PASS/BLOCKED decision plus every individual control result.
- CLI:
  - `python -m capt_runtime.security_gate catalog --json`
  - `python -m capt_runtime.security_gate evaluate --profile ... --evidence ... --source-sha ... --output ...`

## CAPT Core current profile

The initial local-core profile declares:

`local_runtime`, `ipc`, `database`, `local_state`, `ai`, `prompt_processing`, `cli`, `record_store`.

That makes **20 of 46 controls applicable** and **26 explicitly N/A** for the current local-first Core surface. N/A does not mean globally irrelevant: adding the corresponding capability later activates the control.

| ID | Control | Severity | CAPT Core local profile |
|---|---|---|---|
| `VIBE1-01` | Hide API keys | CRITICAL | APPLICABLE — evidence required |
| `VIBE1-02` | Purge Git secrets | CRITICAL | APPLICABLE — evidence required |
| `VIBE1-03` | Use public DB key | HIGH | N/A |
| `VIBE1-04` | Enable row-level security | CRITICAL | N/A |
| `VIBE1-05` | Encrypt sensitive data | HIGH | APPLICABLE — evidence required |
| `VIBE1-06` | Enforce server-side auth | CRITICAL | APPLICABLE — evidence required |
| `VIBE1-07` | Lock record access | CRITICAL | APPLICABLE — evidence required |
| `VIBE1-08` | Block field tampering | HIGH | APPLICABLE — evidence required |
| `VIBE1-09` | Secure session cookies | HIGH | N/A |
| `VIBE1-10` | Hash passwords | CRITICAL | N/A |
| `VIBE1-11` | Rate limit login | HIGH | N/A |
| `VIBE1-12` | Add bot protection | MEDIUM | N/A |
| `VIBE1-13` | Parameterize queries | CRITICAL | APPLICABLE — evidence required |
| `VIBE1-14` | Validate all input | CRITICAL | APPLICABLE — evidence required |
| `VIBE1-15` | Escape user content | HIGH | N/A |
| `VIBE1-16` | Restrict file uploads | HIGH | N/A |
| `VIBE1-17` | Trim API responses | MEDIUM | APPLICABLE — evidence required |
| `VIBE1-18` | Add security headers | HIGH | N/A |
| `VIBE1-19` | Force HTTPS | CRITICAL | N/A |
| `VIBE1-20` | Scan dependencies | HIGH | APPLICABLE — evidence required |
| `VIBE2-01` | Add HSTS | HIGH | N/A |
| `VIBE2-02` | Add CSRF tokens | HIGH | N/A |
| `VIBE2-03` | Reset sessions on password change | HIGH | N/A |
| `VIBE2-04` | Expire reset links | HIGH | N/A |
| `VIBE2-05` | Prevent user enumeration | HIGH | N/A |
| `VIBE2-06` | Whitelist upload types | HIGH | N/A |
| `VIBE2-07` | Verify payment webhooks | CRITICAL | N/A |
| `VIBE2-08` | Set prices server-side | CRITICAL | N/A |
| `VIBE2-09` | Block prompt injection | HIGH | APPLICABLE — evidence required |
| `VIBE2-10` | Cap AI usage | HIGH | APPLICABLE — evidence required |
| `VIBE2-11` | Limit request size | HIGH | APPLICABLE — evidence required |
| `VIBE2-12` | Rate limit password resets | HIGH | N/A |
| `VIBE2-13` | Sanitize before storing | HIGH | APPLICABLE — evidence required |
| `VIBE2-14` | Lock down CORS | HIGH | N/A |
| `VIBE2-15` | Disable directory listing | MEDIUM | N/A |
| `VIBE2-16` | Remove default admin routes | HIGH | N/A |
| `VIBE2-17` | Lock accounts after failed logins | MEDIUM | N/A |
| `VIBE2-18` | Log security events | HIGH | APPLICABLE — evidence required |
| `VIBE2-19` | Set secure cookie flags | HIGH | N/A |
| `VIBE2-20` | Restrict database permissions | CRITICAL | APPLICABLE — evidence required |
| `CAPT-SUP-01` | Authorize every mutation at the authoritative boundary | CRITICAL | APPLICABLE — evidence required |
| `CAPT-SUP-02` | Keep private storage private by default | CRITICAL | N/A |
| `CAPT-SUP-03` | Reject malformed or expired authentication tokens | CRITICAL | N/A for current capability profile |
| `CAPT-SUP-04` | Minimize privileged/debug data crossing into clients | HIGH | APPLICABLE — evidence required |
| `CAPT-SUP-05` | Test denied-access cases, not only happy paths | HIGH | APPLICABLE — evidence required |
| `CAPT-SUP-06` | Treat AI-generated/security-sensitive output as untrusted until verified | HIGH | APPLICABLE — evidence required |

## Current release implication

The baseline evidence file is deliberately empty. Therefore the new gate reports `BLOCKED` until exact-head evidence is supplied for every applicable control.

This is intentional. Existing controls such as gitleaks and pip-audit are useful evidence producers, but merely having them configured is not proof they passed on a particular release SHA. The release workflow should run the producers, record exact-head evidence, then evaluate this gate.

The first CAPT Core security closure campaign therefore needs to prove or repair these 20 applicable controls:

- API-key secrecy and Git-history secret hygiene;
- sensitive-data encryption policy;
- server-side IPC authentication;
- record/database access controls;
- field-tamper and input validation;
- parameterized database access;
- response data minimization;
- dependency vulnerability scanning;
- prompt-injection handling;
- bounded AI usage;
- bounded IPC/request size;
- sanitization before persistence;
- auditable security-event logging;
- database/file permission restriction;
- authoritative mutation authorization;
- client/debug data minimization;
- denied-access regression tests;
- explicit untrusted-AI-output boundary.

Some of these likely already have strong implementation evidence in CAPT. They remain unverified here until exact-source tests or audits are attached. That is a provenance rule, not a claim that the controls are absent.

## Release workflow integration

`.github/workflows/release-security.yml` remains the release security workflow. The security-gate job runs after the existing test/secret jobs, emits a JSON assessment artifact, and fails the release when the assessment is BLOCKED.

The gate is meant to converge with existing evidence producers rather than replace them:

- gitleaks -> `VIBE1-01`, `VIBE1-02`;
- pip-audit -> `VIBE1-20`;
- auth/IPC adversarial tests -> `VIBE1-06`, `CAPT-SUP-03/05` where applicable;
- EventStore/database tests -> `VIBE1-07`, `VIBE1-13`, `VIBE2-20`;
- schema/fuzz tests -> `VIBE1-08`, `VIBE1-14`, `VIBE2-13`;
- AI/prompt adversarial suite -> `VIBE2-09`, `CAPT-SUP-06`;
- lease/accounting tests -> `VIBE2-10`;
- transport framing tests -> `VIBE2-11`;
- audit-event tests -> `VIBE2-18`;
- RuntimeService authority tests -> `CAPT-SUP-01`;
- projection/redaction tests -> `VIBE1-17`, `CAPT-SUP-04`.

## Future CAPT-native integration

The next integration layer should admit a completed `SecurityGateResult` through normal CAPT evidence and verification boundaries:

`scanner/check -> SecurityEvidence -> SecurityGateResult -> CAPT evidence admission -> security-domain verification -> release decision`

The security gate must never write directly to authoritative state. RuntimeService remains the only authority for governed state transitions.

A future Security Governor can add project profile discovery with operator confirmation, scheduled control execution, evidence expiry/freshness policies, per-control verifier adapters, threat-model-aware applicability, signed/expiring accepted-risk decisions, dependency/SBOM and secret-scanner adapters, web-header/TLS/CORS probes, DB/RLS/storage adapters, auth/session/password/payment adapters, AI prompt-injection and usage-budget adversarial suites, TUI/Desktop security status surfaces, and release evidence bundle export.

## Acceptance criteria for this foundation

- all 40 screenshot controls exist with stable IDs;
- profile applicability is deterministic;
- missing applicable evidence blocks release;
- stale PASS evidence blocks release;
- failed evidence blocks release;
- exact-SHA complete evidence can pass;
- N/A controls do not masquerade as PASS;
- unknown/duplicate evidence fails closed;
- the evaluator has no RuntimeService/EventStore mutation path;
- tests cover catalog completeness, applicability, stale evidence, failure, complete pass, malformed evidence, and duplicate/unknown evidence.

No claim is made here that CAPT Core already passes all applicable controls. That requires the security closure audit at the exact terminal release head.
