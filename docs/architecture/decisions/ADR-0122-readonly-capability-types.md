---
status: Accepted (M0-B)
date: 2026-08-03
relates_to: ADR-0120, ADR-0121
---

# ADR-0122 — Read-only capability types

## Context
M0-B must prove read-only capability enforcement: the driver may hold
`RepositoryRead`, `FilesystemRead`, `ArtifactCreate`, `AnalysisOnly` — but
attempting `RepositoryWrite` must fail before dispatch.

## Decision
Add four read-only capability operation names and one forbidden write operation
(`RepositoryWrite`) to the capability operation vocabulary. A `DriverWorkOrder`
may only carry operations drawn from the read-only set. Dispatch rejects any work
order whose operations intersect the write set BEFORE the driver is invoked.
`ArtifactCreate` is permitted because artifact *candidates* are driver output that
CAPT validates; it is not a mutation of CAPT authoritative state.

## Explicit deny list (M0-B)
`repository.write`, `filesystem.write` outside staging, `git.commit`, `git.push`,
`process.mutate`, `package.install`, `deployment`, `credential.use` (unless
separately approved), `unrestricted network`.

## Consequences
- `CapabilityAggregate.check_lease` already validates `operation ∈ lease.operations`;
  the read-only set is enforced at work-order construction and at dispatch.
- `RepositoryWrite` is never a legal operation for a driver lease in M0-B.

## Reversal conditions
Only if a future gate explicitly introduces write capabilities (M0-C+); out of
scope for M0-B.
