# CAPT Runtime M0 Contract Inventory

Frozen version: **contractSchemaVersion 1.0.0** (instance `SchemaVersion` const "1.0.0").
Generated bindings: Python `capt_contracts.types` / TS `types.ts` (regenerated from
schema; drift check clean). All symbols below are confirmed present in both
generated bindings.

Authority classification:
- **AUTHORITATIVE** — emitted/owned by CAPT runtime (aggregates, ledger, verification).
- **UNTRUSTED** — produced by an external ExecutionDriver; CAPT validates before promotion.
- **SHARED** — referenced by both; ownership stays with CAPT.

Compatibility policy: patch / minor / major (see `CAPT_RUNTIME_M0_COMPATIBILITY_POLICY.md`).

| # | Contract | Canonical schema | Schema ver | TS symbol | Py symbol | Owning aggregate / subsystem | M0 origin | Authority class | Compat policy |
|---|----------|-----------------|-----------|-----------|-----------|------------------------------|-----------|-----------------|--------------|
| 1 | MissionSpec | mission.schema.json | 1.0.0 | MissionSpec | MissionSpec | MissionAggregate | M0-A | AUTHORITATIVE | minor (additive) |
| 2 | TaskGraph | task.schema.json | 1.0.0 | TaskGraph | TaskGraph | TaskAggregate | M0-A | AUTHORITATIVE | minor |
| 3 | PolicyDecision | policy.schema.json | 1.0.0 | PolicyDecision | PolicyDecision | GovernanceKernel | M0-A | AUTHORITATIVE | minor |
| 4 | Capability | capability.schema.json | 1.0.0 | Capability | Capability | CapabilityAggregate | M0-A | AUTHORITATIVE | minor |
| 5 | CapabilityGrant | capability.schema.json | 1.0.0 | CapabilityGrant | CapabilityGrant | CapabilityAggregate | M0-A | AUTHORITATIVE | minor |
| 6 | CapabilityLease | capability.schema.json | 1.0.0 | CapabilityLease | CapabilityLease | CapabilityAggregate | M0-A | AUTHORITATIVE | minor |
| 7 | CapabilityReservation | capability.schema.json | 1.0.0 | CapabilityReservation | CapabilityReservation | CapabilityAggregate | M0-A | AUTHORITATIVE | minor |
| 8 | CapabilityConsumptionRecord | capability.schema.json | 1.0.0 | CapabilityConsumptionRecord | CapabilityConsumptionRecord | CapabilityAggregate (ledger) | M0-A | AUTHORITATIVE | minor |
| 9 | CapabilityRevocation | capability.schema.json | 1.0.0 | CapabilityRevocation | CapabilityRevocation | CapabilityAggregate | M0-A | AUTHORITATIVE | minor |
| 10 | ToolRequest | tool.schema.json | 1.0.0 | ToolRequest | ToolRequest | Execution (tool layer) | M0-A | AUTHORITATIVE | minor |
| 11 | ToolResult | tool.schema.json | 1.0.0 | ToolResult | ToolResult | Execution (tool layer) | M0-A | AUTHORITATIVE | minor |
| 12 | ClaimRecord | claim.schema.json | 1.0.0 | ClaimRecord | ClaimRecord | ClaimAggregate | M0-A | AUTHORITATIVE | minor |
| 13 | EvidenceRecord | evidence.schema.json | 1.0.0 | EvidenceRecord | EvidenceRecord | VerificationPipeline | M0-A | AUTHORITATIVE | minor |
| 14 | VerificationResult | verification.schema.json | 1.0.0 | VerificationResult | VerificationResult | VerificationPipeline | M0-A | AUTHORITATIVE | minor |
| 15 | ClaimGuardDecision | claim.schema.json | 1.0.0 | ClaimGuardDecision | ClaimGuardDecision | ClaimGuard | M0-A | AUTHORITATIVE | minor |
| 16 | CheckpointManifest | checkpoint.schema.json | 1.0.0 | CheckpointManifest | CheckpointManifest | CheckpointStore | M0-A | AUTHORITATIVE | minor |
| 17 | EventEnvelope | event.schema.json | 1.0.0 | EventEnvelope | EventEnvelope | EventLedger | M0-A | AUTHORITATIVE | minor |
| 18 | ExecutionDriverDescriptor | driver.schema.json | 1.0.0 | ExecutionDriverDescriptor | ExecutionDriverDescriptor | DriverRegistry | M0-B | AUTHORITATIVE (registry) | minor |
| 19 | ExecutionDriverWorkOrder | driver.schema.json | 1.0.0 | ExecutionDriverWorkOrder | ExecutionDriverWorkOrder | DriverHost (CAPT-built) | M0-B | AUTHORITATIVE (CAPT-built) | minor |
| 20 | DriverObservation | evidence.schema.json | 1.0.0 | DriverObservation | DriverObservation | ExecutionDriver (untrusted) | M0-B | UNTRUSTED | minor |
| 21 | DriverArtifactCandidate | driver.schema.json | 1.0.0 | DriverArtifactCandidate | DriverArtifactCandidate | ExecutionDriver (untrusted) | M0-B | UNTRUSTED | minor |
| 22 | DriverReceiptCandidate | driver.schema.json | 1.0.0 | DriverReceiptCandidate | DriverReceiptCandidate | ExecutionDriver (untrusted) | M0-B | UNTRUSTED | minor |
| 23 | DriverClaimProposal | evidence.schema.json | 1.0.0 | DriverClaimProposal | DriverClaimProposal | ExecutionDriver (untrusted) | M0-B | UNTRUSTED | minor |
| 24 | DriverRunState | driver.schema.json | 1.0.0 | DriverRunState | DriverRunState | DriverRunAggregate | M0-B | AUTHORITATIVE (driver-run only) | minor |
| 25 | DriverRunCheckpoint | driver.schema.json | 1.0.0 | DriverRunCheckpoint | DriverRunCheckpoint | DriverRunAggregate / CheckpointStore | M0-B | AUTHORITATIVE | minor |
| 26 | DriverReconciliationResult | driver.schema.json | 1.0.0 | DriverReconciliationResult | DriverReconciliationResult | DriverHost (CAPT reconciliation) | M0-B | AUTHORITATIVE (CAPT-computed) | minor |
| 27 | (ContextSlice, DriverProgressSignal, DriverBudget, etc.) | driver.schema.json | 1.0.0 | various | various | DriverHost / ExecutionDriver | M0-B | SHARED/UNTRUSTED | minor |

## Notes

- **M0-A types (1–17):** owned by CAPT aggregates/ledger/verification. Drivers never
  emit these; they are CAPT-authored authoritative records.
- **M0-B types (18–26):** the driver contract surface. `ExecutionDriverDescriptor`
  and `ExecutionDriverWorkOrder` are CAPT-authored (registry / host-built). The four
  `Driver*` untrusted types (Observation / ArtifactCandidate / ReceiptCandidate /
  ClaimProposal) are produced by the driver and validated by `ingestion.py` before
  any promotion. `DriverRunState` / `DriverRunCheckpoint` are owned by
  `DriverRunAggregate` (driver-run lifecycle only). `DriverReconciliationResult` is
  computed by CAPT (`reconciliation.py`), not the driver.
- **No external OpenHarness types** appear in the contract set. The M0-B driver is a
  CAPT reference implementation; no external schema or package is referenced.
- **Wire shape frozen at 1.0.0.** Additive fields require schema review + ADR note;
  breaking changes require major version bump + ADR.

## Verification of inventory

- Schema source: `contracts/schema/*.json` (`$defs` enumeration, 27 driver + M0-A types).
- Generated Python: `contracts/generated/python/capt_contracts/types.py` — all symbols present.
- Generated TS: `contracts/generated/typescript/src/types.ts` — all symbols present.
- Drift: `contracts/tools/check_drift.py` → DRIFT CHECK: OK (11 generated files match schema).
