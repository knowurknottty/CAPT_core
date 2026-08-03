# CAPT Runtime M0 Authority & Ownership Matrix

Frozen with M0. Verified against code on M0-B HEAD `0d851c4535d2f93c3420f4c6d860f4ecd7285163`
(see `CAPT_RUNTIME_M0_FREEZE_VERIFICATION.md`). The matrix preserves the M0
invariants:

- **Cognition proposes.** (Mission/Task/Claim drafts are proposed, not authoritative.)
- **Governance authorizes.** (GovernanceKernel / PolicyEngine issue PolicyDecision + CapabilityGrant.)
- **Execution performs only authorized work.** (ExecutionDriver runs under a scoped lease.)
- **Verification establishes evidence support.** (VerificationPipeline produces VerificationResult/EvidenceRecord.)
- **ClaimGuard controls claim acceptance/promotion.** (ClaimGuard gates ClaimRecord promotion.)
- **Drivers return untrusted observations only.** (DriverObservation/ArtifactCandidate/ReceiptCandidate/ClaimProposal are untrusted; CAPT validates.)
- **Drivers cannot mutate authoritative CAPT state.**

Legend: ✓ = yes, ✗ = no, R = read-only/observes, U = untrusted input.

| Aggregate / domain | Owns | May read | May mutate | May emit authoritative events | Forbidden authority |
|--------------------|-------|----------|-----------|-------------------------------|---------------------|
| MissionAggregate | mission lifecycle, MissionSpec, objectives, success criteria | its own state | its own state | MissionState transitions | granting capabilities; verifying claims; driver control |
| TaskAggregate | task graph, TaskGraph, dependencies, recovery | its own state | its own state | TaskState transitions | capability grants; claim verification |
| CapabilityAggregate | capabilities, grants, leases, reservations, consumption, revocation | capability ledger | capability ledger | CapabilityGrant / CapabilityLease / CapabilityConsumptionRecord / CapabilityRevocation | delegating authority to drivers; claim promotion |
| DriverRunAggregate | driver-run lifecycle + reconciliation state only | its own run state | its own run state (`driverrun.*`) | DriverRunState / DriverRunCheckpoint | mission/task/capability/claim state; authoritative events beyond run scope |
| ClaimAggregate | claim records, promotion state | its own claims | its own claims | ClaimRecord / ClaimPromotionState | authoring PolicyDecision; granting capabilities |
| GovernanceKernel | policy decisions, authorization | policy + capability state (read) | PolicyDecision | PolicyDecision | executing work; mutating mission/task directly |
| VerificationPipeline | verification + evidence | artifacts, observations (untrusted) | VerificationResult / EvidenceRecord | VerificationResult / EvidenceRecord | granting capabilities; marking completion |
| ClaimGuard | claim acceptance/promotion gate | proposed claims + verification | ClaimGuardDecision | ClaimGuardDecision | authoring claims; executing work |
| DriverRegistry | driver descriptor registry + registration audit | registered descriptors | registration / disable / unregister | DriverRegistered / DriverDisabled (registration_only, trust=untrusted) | capability authority; runtime-global state |
| ExecutionDriver | NOT an aggregate — returns untrusted outputs | context slice (read-only), staging (write artifact) | NOTHING authoritative | NONE (may not emit authoritative events) | mutating Mission/Task/Capability/Claim; emitting EventEnvelope/CapabilityGrant/VerificationResult/ClaimGuardDecision/PolicyDecision; marking completion |
| EventLedger | transactional event log | all events | append (via aggregates) | EventEnvelope (immutable) | driver write access |
| CheckpointStore | per-aggregate checkpoints | checkpoint manifests | CheckpointManifest | CheckpointManifest | driver write access to authoritative checkpoints |

## Code-vs-doc reconciliation

Verified on M0-B HEAD:
- `capt_runtime/drivers/__init__.py` documents that the driver **never receives**
  GovernanceKernel, PolicyEngine, ClaimGuard, CapabilityAggregate, EventLedger, or
  aggregate-mutation authority.
- `capt_runtime/drivers/` + `driver_host.py` contain **no imports** of
  MissionAggregate / TaskAggregate / CapabilityAggregate / ClaimAggregate /
  EventLedger / EventStore, and no calls that emit authoritative CAPT events.
- `DriverRunAggregate.OWNED_FIELDS` is scoped to `driverrun.*` (state,
  reconciliationStatus, workOrderVersion, externalRunId, attemptCount,
  observationSequence, cancellationState, suspensionState, checkpointRef,
  reconciliationState, budgetConsumed, terminalDisposition). It does **not** own
  mission/task/capability/claim fields.
- `DriverRegistry` audit events carry `"authority": "registration_only"` and
  `"trustClassification": "untrusted"` — registration lifecycle only, not CAPT
  authoritative state.
- `verification.py` (incl. `guard_claim` / ClaimGuard) is CAPT-owned; the driver
  does not call into it and cannot promote claims.

**Classification of any discrepancy:** none found. Code and matrix agree. No
documentation defect, no implementation defect, no ambiguous boundary detected in
the M0-B scope.

## Forbidden driver authority (explicit)

An ExecutionDriver MUST NOT:
- mutate MissionAggregate, TaskAggregate, CapabilityAggregate, ClaimAggregate;
- append EventLedger entries;
- issue CapabilityGrants / CapabilityLeases;
- create VerificationResults / EvidenceRecords / ClaimGuardDecisions / PolicyDecisions;
- mark tasks or missions complete;
- emit any authoritative event.

It MAY only return: observations, artifact candidates, receipt candidates, progress
signals, diagnostics, claim proposals — all treated as untrusted until validated by
`ingestion.py` and promoted by CAPT verification.
