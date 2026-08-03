# CAPT Runtime M0 Freeze

Status: **FROZEN** (documentation-only boundary lock; no runtime code change).
Date: 2026-08-03
Branch: `docs/capt-runtime-m0-freeze` (based on M0-B HEAD `0d851c4535d2f93c3420f4c6d860f4ecd7285163`)
Scope: M0-A (Contract & State Proof) + M0-B (Read-Only ExecutionDriver Proof)

## What M0 is

### M0-A — Contract and state proof
- Language-neutral contract source (JSON Schema 2020-12 under `contracts/schema/`).
- Generated Python bindings (`contracts/generated/python/capt_contracts`).
- Generated TypeScript bindings (`contracts/generated/typescript`).
- Aggregate ownership (Mission / Task / Capability / Claim / DriverRun).
- Transactional event ledger (`EventEnvelope`, optimistic concurrency).
- Outbox semantics.
- Capabilities, grants, leases, reservation, consumption, revocation.
- Checkpointing, replay, idempotency.
- Claim / evidence / verification contracts.
- Authority conformance tests.

### M0-B — Read-only ExecutionDriver proof
- Narrow `ExecutionDriver` contract (drivers/__init__.py Protocol).
- `DriverRegistry` (registration audit, identity, disable).
- `DriverRunAggregate` (driver-run lifecycle + reconciliation only).
- Read-only capability model (`capability.py`: allow/deny lists, lease re-validation).
- Context minimization (`context_slice.py` + over-disclosure guard).
- Untrusted observation ingestion (`ingestion.py`).
- Artifact and receipt validation.
- Read-only repository inspection (OpenHarnessDriver reference driver).
- No target-repository mutation.
- Driver restart/reconciliation.
- Replay without re-execution.
- Truthful bounded completion claims (ClaimGuard).

## What the freeze means

The following are **locked** for the M0 scope:

1. **No breaking schema changes** without an ADR and explicit version bump.
2. **No aggregate ownership changes** without an ADR.
3. **No widening of driver authority** beyond the M0-B contract.
4. **No new side-effect capability** added under M0.
5. **No direct external harness types** in CAPT public contracts.
6. **No replacement** of generated bindings by hand-maintained language-specific models.
7. **No weakening** of replay, idempotency, or verification tests.
8. **No claims** that M0 includes external OpenHarness integration. The M0-B driver
   is a locally-implemented CAPT reference driver inspired by OpenHarness.

The following remain **allowed**:

- Bug fixes (behavior-preserving corrections).
- Documentation corrections.
- Additive backward-compatible fields (require schema review + ADR note).

The following are **out of scope** and must occur on a separate branch with
explicit authorization:

- M0-C (governed repository-write proof).
- RuntimeAggregate implementation.
- RuntimeManifest / RuntimeIdentity implementation.
- Integration of another (external) driver.

## Frozen version

- Contract schema version: **1.0.0** (`contracts/schema/index.json` →
  `contractSchemaVersion`).
- Instance `SchemaVersion` const: **"1.0.0"** (`contracts/schema/common.schema.json`).
- These are intentionally kept in lockstep; a bump requires ADR + regeneration +
  drift check.

## Companion documents (this freeze set)

- `CAPT_RUNTIME_M0_CONTRACT_INVENTORY.md` — 27+ contract types, symbols, ownership, policy.
- `CAPT_RUNTIME_M0_AUTHORITY_MATRIX.md` — aggregate/domain authority ownership.
- `CAPT_RUNTIME_M0_DRIVER_BOUNDARY.md` — explicit ExecutionDriver input/output boundary.
- `CAPT_RUNTIME_M0_COMPATIBILITY_POLICY.md` — patch/minor/major policy.
- `CAPT_RUNTIME_M0_FREEZE_VERIFICATION.md` — fresh verification evidence.
- `CAPT_RUNTIME_M0_FREEZE_TRIPLE_RECURSION_LEDGER.md` — construct/adversarial/reconcile ledger.

## Cross-links

- Architecture spec: `docs/architecture/CAPT_RUNTIME_ARCHITECTURE_SPEC.md`
  (branch `docs/capt-runtime-architecture-spec`).
- M0 workflow: `docs/workflows/CAPT_RUNTIME_CONTRACTS_AND_M0_IMPLEMENTATION_WORKFLOW.md`.
- M0-A evidence: `docs/architecture/M0A_FORENSIC_AND_GAP.md` (M0-B branch).
- M0-B evidence: `docs/architecture/M0B_RUNTIMEAGGREGATE_EVIDENCE.md`,
  `docs/architecture/M0B_TRIPLE_RECURSION_LEDGER.md` (M0-B branch).
- M0-B acceptance: `docs/architecture/governance/M0B_ACCEPTANCE_DECISION.md`
  (branch `docs/post-m0b-governance-review`).
- RuntimeAggregate ADR proposal: `docs/architecture/governance/POST_M0B_RUNTIMEAGGREGATE_ADR_PROPOSAL.md`.
- Release Security decision: `docs/architecture/governance/RELEASE_SECURITY_DEPENDENCY_DECISION.md`.

## RuntimeAggregate / RuntimeManifest status

M0 has **no RuntimeAggregate** and **no mutable runtime-global state owner**.
Any future runtime identity/manifest contract requires a separately authorized
ADR and must not duplicate existing aggregate ownership (see
`CAPT_RUNTIME_M0_AUTHORITY_MATRIX.md` and the ADR proposal).

## Governance note

The earlier `POST_M0B_GOVERNANCE_INCIDENT_REPORT.md` records an observed
skill self-improvement message (a one-line patch to a user-level Hermes skill,
`verification-workflows/SKILL.md`). That activity belongs to the **separate
bioCAPT Ouroboros self-improvement subsystem**, which operates outside the CAPT
worktree and is not controlled by this harness agent. It did **not** modify the
CAPT repository or any CAPT runtime code, and it does **not** invalidate the M0-B
runtime evidence. It is retained as historical evidence only.
