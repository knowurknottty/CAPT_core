---
status: Accepted (M0-B)
date: 2026-08-03
relates_to: spec §6.4, ADR-0110, ADR-0111
---

# ADR-0120 — Driver trust boundary

## Context
M0-A proved transactional state, aggregate ownership, and capability lifecycle
with `DriverRunAggregate` as contract+state model only (ADR-0111). M0-B must
integrate a real untrusted external ExecutionDriver without granting it
constitutional authority over CAPT state.

## Decision
The driver is a pure function from a `ContextSlice` + capability lease to a
stream of untrusted outputs (observations, artifact candidates, receipt
candidates, progress signals, claim proposals). CAPT validates those outputs and
is the ONLY actor that may create `EvidenceRecord`, `ClaimRecord`, authoritative
`EventEnvelope`s, `VerificationResult`, capability-consumption records, task
completion, or mission completion. The driver never receives `GovernanceKernel`,
`PolicyEngine`, `ClaimGuard`, `CapabilityAggregate`, `EventLedger`, or any
aggregate-mutation authority.

## Alternatives considered
- "Driver writes directly to the event ledger": rejected — collapses the trust
  boundary; an untrusted process could forge authoritative events.
- "Driver holds a restricted aggregate reference": rejected — any reference is a
  path to mutation; authority must be structural, not convention.
- "Trust the driver's self-reported success": rejected — that is exactly the
  claim-integrity failure M0-A's ClaimGuard exists to prevent.

## Consequences
- All driver output is `trust: untrusted` until CAPT verifies it.
- CAPT's verification pipeline is the single promotion point.
- The driver cannot complete a task or mission; only CAPT can.

## Reversal conditions
Only if a future gate formally promotes a driver to a trusted in-process
component with its own authority plane — out of scope for M0-B.

## Evidence
- `capt_runtime/authority.py`: `EXTERNAL_DRIVER` kind exists; not in any
  `_PERMITTED` set for authoritative acts.
- `contracts/schema/evidence.schema.json`: `DriverObservation`/`DriverClaimProposal`
  are Family B (untrusted), structurally non-substitutable with `EvidenceRecord`.
