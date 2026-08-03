# CAPT Runtime M0 ExecutionDriver Boundary

Frozen with M0. This document states the explicit input/output contract for an
ExecutionDriver. It is derived from `capt_runtime/drivers/__init__.py`
(`ExecutionDriver` Protocol) and `capt_runtime/driver_host.py` (`build_context`,
`dispatch`). No implementation change is made here.

## Drivers receive (CAPT-built, passed by DriverHost)

1. **One bounded work order** — `ExecutionDriverWorkOrder` (schema 1.0.0). Single
   scoped task; no ambient authority.
2. **Context slice** — `ContextSlice`: minimized, over-disclosure-guarded view of
   what the driver may see. Authority objects (GovernanceKernel, PolicyEngine,
   ClaimGuard, CapabilityAggregate, EventLedger, etc.) are rejected by
   `context_slice.py`.
3. **Permitted tools** — explicit allowlist; no tool beyond the list is available.
4. **Scoped capability leases** — `CapabilityLease` with bounded operations,
   resource scope, budget, and validity window. Re-validated by `capability.py`
   before every external call.
5. **Filesystem policy** — `FilesystemPolicy` (rootPath, allowedPaths, writesAllowed=false).
6. **Network policy** — `NetworkPolicy` (egressAllowed=false by default).
7. **Budgets** — `DriverBudgets` (maxSeconds, maxArtifacts, maxObservations).
8. **Expected artifacts** — `ExpectedArtifact[]` (staging paths only).
9. **Required receipts** — `RequiredReceipt[]`.
10. **Termination conditions** — `DriverTerminationCondition` (e.g. onUnexpectedWrite=fail).

## Drivers may return (all UNTRUSTED)

- **Observations** — `DriverObservation` (`trust: untrusted`, `observedBy` must
  match the verified driver id; validated by `ingestion.py`).
- **Artifact candidates** — `DriverArtifactCandidate` (written only to the
  designated staging root; path/symlink-escape rejected).
- **Receipt candidates** — `DriverReceiptCandidate`.
- **Progress signals** — `DriverProgressSignal`.
- **Diagnostics** — driver-local diagnostics.
- **Claim proposals** — `DriverClaimProposal` (bounded; gated by ClaimGuard).

## Drivers may NOT authoritatively create or mutate

- `PolicyDecision`
- `CapabilityGrant`
- `CapabilityLease`
- `CapabilityConsumptionRecord`
- Mission state
- Task state
- `ClaimRecord`
- `EvidenceRecord`
- `VerificationResult`
- `ClaimGuardDecision`
- `EventLedger` entries
- completion state

## Reference driver classification

The M0-B driver (`OpenHarnessDriver` in `capt_runtime/drivers/openharness.py`) is a
**CAPT reference ExecutionDriver inspired by OpenHarness**. It performs REAL
read-only local repository inspection (filesystem walk, metadata read) and writes
one analysis artifact to the staging directory. It does **not** import,
subprocess-invoke, or call any external OpenHarness project, package, executable,
or service. It is **not** a real external OpenHarness integration and **not** an
adapter over an installed OpenHarness runtime.

## Future external-driver conformance requirement (NOT implemented)

When/if an external driver is integrated (post-M0, separately authorized), it must
satisfy a conformance suite proving, against the contract above:
- it receives only the bounded work order + context slice + scoped lease;
- it returns only untrusted observations/artifacts/receipts/progress/diagnostics/claim proposals;
- it cannot emit any authoritative CAPT type;
- it performs no target-repository mutation, no git mutation, no shell mutation;
- its observations pass `ingestion.py` validation (including `observedBy` match);
- its artifact candidates are confined to staging and pass digest validation;
- completion claims are bounded and pass ClaimGuard.

This requirement is specified but **not implemented** in M0.
