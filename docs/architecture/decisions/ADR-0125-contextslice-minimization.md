---
status: Accepted (M0-B)
date: 2026-08-03
relates_to: ADR-0120
---

# ADR-0125 — ContextSlice minimization

## Context
The driver must receive only `ContextSlice`, capability leases, permitted tools,
budgets, filesystem policy, expected artifacts, and termination conditions. It
must NEVER receive `GovernanceKernel`, `PolicyEngine`, `ClaimGuard`,
`CapabilityAggregate`, `EventLedger`, or aggregate mutation authority.

## Decision
`ContextSlice` is a deliberately minimal, read-only projection. It contains: a
scoped filesystem view (root + allowed paths, `writesAllowed: false`), the active
lease (operations + scope + validity window), `networkPolicy` (`egressAllowed:
false`), permitted tool names, budgets, expected artifact descriptors, and
termination conditions. It explicitly EXCLUDES any reference to governance,
policy, claim, capability graph, ledger, or aggregate internals. Context
over-disclosure is a build-time contract violation: `DriverHost` constructs
`ContextSlice` and asserts the excluded objects are absent.

## Consequences
- `ContextSlice` is constructed by CAPT (`DriverHost`), never by the driver.
- A test asserts that passing a `GovernanceKernel`/`EventLedger` reference into
  `ContextSlice` construction raises.

## Reversal conditions
None for M0-B.
