# ARCHITECTURAL_PATTERNS — Reusable CAPT Patterns

Status: RECOVERED (knowledge archaeology pass, 2026-07-30)
Purpose: extract reusable design patterns developed across CAPT. These are
patterns, not isolated implementations — apply them to future subsystems.

## P1. Validator Gate (fail-closed)
- Pattern: a release/verification check returns `{check_id, status, evidence}`.
  Any `fail` makes the whole result `ok: False`. Never silent-pass.
- Implemented: `capt_solo/release_validation.py` (`_check`, `result_document`).
- Reuse: any new gate (security, schema, provenance) follows this shape.
- Principle: ADR-0006 evidence over implementation.

## P2. Governance Transaction (audited mutation)
- Pattern: wrap any consequential action in begin→fn→commit/abort with a named
  actor, correlation_id, and receipt. On failure, abort + record.
- Implemented: `capt_solo/ctp/journal.py` (CTP). Conceptual wrapper: GOVERNANCE.md.
- Reuse: publish/deprecate/revoke/approve/install all use this.

## P3. Capability Registry (single catalog)
- Pattern: one YAML catalog of all capabilities with status, owning ADRs, public
  tier. Code conforms to it; drift is visible.
- Implemented: `architecture/registry.yaml` + `validate_registry.py`.
- Reuse: new subsystems register here first; status drives roadmap.

## P4. Receipt System (immutable proof of action)
- Pattern: every committed transaction emits a frozen `Receipt` (tx_id, status,
  timestamps, meta). Receipts are the audit primitive.
- Implemented: `capt_solo/ctp/journal.py::Receipt`.
- Reuse: Governance, Knowledge Bubbles install, release metadata all emit receipts.

## P5. Provenance Tracking (hash + scope + trust)
- Pattern: every evidence/artifact carries source, hash, trust(0–1), scope,
  expiry. Stale (>TTL) excluded unless renewed.
- Implemented: `capt_solo/evidence/` (EvidenceSource/Record), `memory/secrets.py`.
- Reuse: any persisted fact gets provenance fields.

## P6. VSI State-Binding (verification attaches to state)
- Pattern: a verification result is keyed to a VerifiedStateIdentity (repo, branch,
  HEAD, scoped hashes, deps, runtime, env, command, scope). Equivalent states →
  reused verification. Untracked artifacts excluded from equivalence.
- Implemented: `capt_solo/verification/identity.py`.
- Reuse: test caching, CI gating, evidence reuse all key on VSI.

## P7. Plugin / Skill Boundary (degradable by default)
- Pattern: plugins/skills are independently loadable, disabled by default, fail
  safe offline. No core dependency on a plugin.
- Implemented: `capt_solo/plugin/`, Hermes plugin interface.
- Reuse: any extension point follows this boundary.

## P8. Degradation-Aware Language (honest failure)
- Pattern: when a capability is degraded, report SCOPED language ("degraded on
  macos only", not "globally revoked"). Never report unverified as verified.
- Implemented: ATE fidelity guards (memory/antitoken.py). Conceptual: ClaimGuard.
- Reuse: any status report uses this contract.

## P9. Option A Release Identity (no self-SHA)
- Pattern: source commit (immutable) + metadata commit (names source ancestor).
  Validator detects context (source vs metadata) and validates candidate_sha
  against the correct target. Mathematically valid; no amend loop.
- Implemented: `capt_solo/release_validation.py` (ancestor check).
- Reuse: any release process that needs provenance without a self-referential SHA.

## P10. Quarantined Import (never auto-trust)
- Pattern: imported artifacts (Knowledge Bubbles) enter quarantined; never
  executable, never overwrite canonical silently; explicit approval + CTP install.
- Implemented: conceptual (CTP substrate shipped).
- Reuse: any cross-instance data import.

## P11. Local-First Transport (opt-in network)
- Pattern: no operation requires network; remote transports are opt-in and fail
  safe offline (ADR-0005).
- Implemented: ATE (local stdio → upstream MCP), PULSE (optional plugin).
- Reuse: any I/O boundary.

## P12. Evidence Continuum (distinct states, no collapse)
- Pattern: present/believed/inferred/attempted/changed/verified/valid/invalidated
  are SEPARATE fields/concepts, never merged into one "status" (ADR-0011).
- Implemented: `capt_solo/evidence/` (EvidenceRecord classes).
- Reuse: any epistemic state machine.

## Cross-reference
These patterns map to the Treasure Chest (#1–#20) and the ADRs (#1–#12). They are
the "how" behind the "what". Future contributors: when adding a subsystem, check
this list first — most problems already have a pattern.
