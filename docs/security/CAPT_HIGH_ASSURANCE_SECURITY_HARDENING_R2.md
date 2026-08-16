# CAPT High-Assurance Security Hardening Addendum

Status: DESIGN/IMPLEMENTATION QUEUE FOR PR #49
Date: 2026-08-16
Scope: `feat/security-infrastructure-gate` stacked on PR #48

## Purpose

The screenshot checklist is valuable, but CAPT's security objective is stronger than a one-time pre-launch audit. Security controls must be represented as infrastructure, exact-head evidence, and governed release conditions so that new capabilities activate their own security obligations automatically.

This addendum integrates the operator-supplied checklist, the supplied current-state critique, and the current CAPT architecture without weakening CAPT's authority boundaries.

## Source reconciliation

### Screenshot controls

The executable PR #49 catalog preserves all 40 controls visible in the two supplied screenshots: 20 `VIBE1-*` controls and 20 `VIBE2-*` controls.

### Notion/PDF "do these first" controls

The supplied PDF exposes seven priority controls:

1. keep API keys and secrets server-side;
2. use public rather than admin database keys on clients;
3. enable row-level security;
4. prove record/tenant ownership isolation, not merely authentication;
5. rate-limit APIs, especially login and metered calls;
6. set billing caps and alerts on paid services;
7. use parameterized queries.

Six map directly to existing `VIBE1-*`/`VIBE2-*` controls. **Billing caps and alerts is the one unique source requirement not fully represented by the 40 screenshot titles.** Before PR #49 may leave draft, add a stable executable control for paid-service billing caps/alerts (recommended ID `CAPT-SUP-07`) or explicitly broaden `VIBE2-10` with a source-preserving sub-requirement and regression evidence. Do not silently pretend "Cap AI usage" already proves generic paid-service billing controls.

The full Notion body could not be fetched by the review environment, so no unseen item is invented. Any later unique Notion item gets a new stable control ID.

## High-assurance trust-hardening requirements from the CAPT critique

These requirements are not replacements for the 40 source controls. They are CAPT-specific security invariants that should become supplemental gate controls or explicit release prerequisites.

### HA-01 - Authenticate the existing EventStore hash chain

CAPT already has `payload_digest`, `chain_digest`, and chain verification. The missing property is **independent authentication**, not hashing.

Required direction:

`Event hash chain -> signed checkpoint root -> hardware/OS-protected key -> optional external/offline anchor`

Required semantics must distinguish at least:

- `CHAIN_VALID`
- `SIGNATURE_VALID`
- `EXTERNAL_ANCHOR_VALID`

A locally recomputable hash chain must never be described as proof against a host attacker who can rewrite the database and recompute hashes. A signing key stored beside the database also does not close that threat.

### HA-02 - Encrypt persistent state without turning memory into a credential vault

General CAPT persistent state remains plaintext unless host/disk protection is present. The high-assurance track should separate:

- whole-database/local-state encryption;
- selective envelope encryption for especially sensitive memory/evidence/artifacts;
- export/backup encryption;
- credential storage by reference to Keychain/environment/other protected secret stores.

Invariant: **memory != credential vault**. Encryption does not justify placing raw provider credentials in MemoryEngine/EventStore.

### HA-03 - Require execution isolation before write-capable autonomous drivers

Current Hermes remains read-only. Security hardening must not falsely describe today's read-only adapter as unrestricted code execution.

Before write-capable engineering is enabled, select an isolation profile at the execution/workspace plane, e.g.:

- read-only native driver;
- restricted workspace subprocess;
- OS sandbox;
- container/microVM;
- explicitly trusted host execution.

Governance remains in RuntimeService/capability policy. Sandboxing sits underneath the driver boundary; it does not become a second authority plane.

### HA-04 - Keep KHSB internal; add remote transport as a separate governed boundary

KHSB is intentionally in-process. CAPT already has authenticated Unix-domain-socket IPC. If remote/federated CAPT is added, do not make KHSB authoritative merely to get networking.

A future CAPT Transport/Relay requires:

- mutual device identity;
- encrypted channels;
- replay protection;
- capability-bound operations;
- remote-node provenance/attestation where appropriate;
- durable inbox/outbox semantics;
- offline reconciliation;
- sequence/epoch handling;
- revocation;
- final admission through RuntimeService.

### HA-05 - Preserve the Solo security profile; add Multi-Principal only when the product surface requires it

Current CAPT Solo assumes one trusted local OS operator. That is an explicit threat-model boundary, not automatically a defect.

If a shared/team/SaaS/mutually-untrusted-agent profile is introduced, it must activate a separate multi-principal security profile covering principals, namespaces, ownership, ACL/ABAC/RBAC, per-principal capability grants, memory/evidence isolation, key isolation, delegated authority, revocation, tenant-safe retrieval, and audit identity.

Do not contaminate Solo with a partial IAM system just to tick a checklist box.

### HA-06 - Exact integrated-stack proof is a security control

The current `.7` train is stacked across Discovery -> lifecycle/Ouroboros -> Prompt/Provenance -> Cohort -> Security Gate. Security acceptance is not inherited from intermediate SHAs.

Before release:

- reconcile/merge in dependency order;
- run exact-terminal-head tests;
- run installed-wheel acceptance from the resulting integrated state;
- regenerate security evidence from that exact source tree;
- refuse a green security gate if any evidence comes only from an ancestor.

### HA-07 - Cohort durability must precede durable multi-perspective security claims

Current Cohort work is a non-authoritative projection/state-machine slice. Before CAPT claims durable multi-agent convergence, complete and test:

- RuntimeService/EventStore persistence;
- reconstruction;
- durable cursor/restart semantics;
- evidence admission;
- governed participant scheduling;
- installed-runtime/TUI dogfood.

Security-related dissent/escalation cannot be treated as durable merely because in-memory Cohort projections exist.

### HA-08 - Reciprocal adversarial review findings are release inputs, not disposable review prose

The Terra/DeepSeek reciprocal process surfaced real defects in prompt-provenance, Unicode/indirect prompt-injection handling, authoritative approval binding, and Cohort convergence semantics. PR #49 should consume the **terminal cross-verified dispositions**, not freeze today's intermediate findings as truth.

Before PR #49 acceptance, require a terminal reciprocal-review status or explicit operator override. Any surviving HIGH/CRITICAL finding relevant to a security control must keep the corresponding gate control red or unverified.

## Architecture-preservation rules

Security work must not make CAPT less coherent:

- signing does not replace EventStore;
- encryption does not make MemoryEngine a secret vault;
- distributed IPC does not make KHSB authoritative;
- sandboxing does not move governance into drivers;
- multi-user support does not silently change the Solo threat model;
- scanner output does not become verification, claim acceptance, task completion, mission completion, or capability authority;
- a release gate may consume CAPT evidence but must not mint authoritative state itself.

## Secure-development framework mapping

PR #49 should treat the checklist as a CAPT-specific secure-development profile, not as security folklore. The implementation should map evidence producers and release tasks to a durable secure-development framework:

- organization/release preparation;
- protection of source/build/release artifacts;
- production of well-secured software;
- vulnerability response and recurrence prevention;
- AI-specific secure-development practices for prompt/context/tool boundaries.

This mapping is documentary/evidence taxonomy only. External frameworks do not become CAPT authority.

## PR #49 next-assignment queue

After the Terra/DeepSeek reciprocal cycle reaches green-light/terminal adjudication, the next agents must execute in this order:

1. Re-fetch PR #49, PR #48, PR #47 and terminal reciprocal-review heads.
2. Reconcile PR #49 onto the final accepted stack head without force-push/history rewrite.
3. Reconcile the PDF priority seven against the executable control catalog; add the unique billing-caps/alerts requirement.
4. Update control applicability from the final capability surface.
5. Convert each currently-applicable control from prose to a real verifier/evidence producer where possible.
6. Close the six R1 blockers already listed in PR #49.
7. Add explicit high-assurance controls or release prerequisites for HA-01 through HA-08.
8. Run secret/dependency/security tests and all new control-specific adversarial tests at the exact head.
9. Run the full repository suite and installed-wheel acceptance at the exact head.
10. Generate ephemeral exact-head security evidence and run the fail-closed gate.
11. Perform a dedicated security diff scan and threat-model review of PR #49.
12. Only then move PR #49 from draft toward review/merge.

## Acceptance rule

PR #49 is not green because a checklist exists. It is green only when every applicable release-blocking control has exact-head evidence, all surviving relevant reciprocal findings are resolved or explicitly governed, and the resulting architecture still preserves CAPT's single authoritative runtime boundary.
