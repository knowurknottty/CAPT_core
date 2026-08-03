# ADR-0107 — Capability grants, leases, reservations, revocation, and consumption

**Status:** Accepted (M0-A)
**Date:** 2026-08-02
**Relates to:** spec §9, ledger Findings D/E/I, workflow Gate 3

## Context

Spec §9 defines a five-stage capability lifecycle. Ledger findings drive three specific requirements:

- **Finding D** — a long-running driver could use authority after approval withdrawal ⇒ revocation must be checked immediately before the effect, not only at work-order issue.
- **Finding E** — a crash between side effect and success recording could cause unsafe replay ⇒ reservation/finalization with an `indeterminate` outcome.
- **Finding I** — grants could not be audited against the exact policy version that authorized them ⇒ bind grants to a `PolicyDecision` id and a policy bundle digest.

Baseline: the existing `CapabilityRegistry` (`capt_solo/foundry/registry.py`) is a *catalogue* answering "can CAPT do X?" with lifecycle `candidate/validated/verified/deprecated/revoked/degraded/experimental`. It has **no** subject, resource, scope, operations, grant, lease, reservation, use limit, validity window, or issuing authority. It cannot be adapted; it is a different concept at a different layer.

## Decision

**A five-stage authorization lifecycle owned exclusively by `CapabilityAggregate`, with revalidation at the effect boundary.**

```
Capability (definition)
   └─ CapabilityRequirement   what a task needs
       └─ CapabilityGrant     scoped authorization to a subject   [PolicyDecision-bound]
           └─ CapabilityLease  grant bound to mission+task+execution context
               └─ CapabilityReservation  one intended consequential use
                   └─ CapabilityConsumptionRecord  outcome: succeeded|failed|indeterminate
```

### Grant
Required fields: `subject`, `capability`, `resource` (typed `ResourceScope` discriminated union), `operations`, `policyDecisionId`, `policyBundleDigest`, `conditions` (discriminated union), `maxUses` (nullable = unlimited), `validFrom`/`validUntil`, `issuedBy`. A grant with no `policyDecisionId` is invalid at schema level — authority cannot exist without a recorded decision that produced it (Finding I).

### Lease
Binds a grant to `missionId` + `taskId` + `executionContextId`. **A lease may only narrow, never widen, its parent grant** — operations must be a subset, scope must be contained, validity window must be inside the grant's. Enforced in `CapabilityAggregate` and tested with scope-widening negative cases.

### Reservation → finalization (two-phase)
```
reserve(leaseId, operationFingerprint, idempotencyKey)   -> reservationId
   ... consequential effect would occur here ...
finalize(reservationId, outcome)                          -> ConsumptionRecord
```
- `reserve` increments `usesConsumed` **immediately**, before the effect. A crash after reserve and before finalize leaves the use consumed and the reservation `open` — fail-closed. It never leaves the budget un-decremented.
- `finalize` outcomes: `succeeded`, `failed`, `indeterminate`.
- `indeterminate` moves the reservation to `awaiting_reconciliation`. The runtime **must not** retry it (ADR-0108). A `reconcile()` call with external evidence is required to resolve it.
- Every finalized reservation produces exactly one `CapabilityConsumptionRecord`. Duplicate finalization of the same reservation raises `DuplicateConsumptionError`.

### Revalidation at the effect boundary
`CapabilityAggregate.validate_for_effect(lease_id, now)` is a **mandatory** call immediately before any consequential effect. It checks, in order: lease exists → lease not revoked → parent grant not revoked → grant not expired → lease not expired → `usesConsumed < maxUses` → requested operation ∈ lease operations → requested resource ⊆ lease scope. Any failure raises `CapabilityDeniedError` with the specific reason.

This is checked **again at reserve time** even if the caller already checked. The revocation race (Finding D) is tested explicitly: revoke between `activate` and `reserve`, assert `reserve` denies.

### Revocation and expiry
- Revocation is an event (`CapabilityGrantRevoked` / `CapabilityLeaseRevoked`), never a field mutation, so it appears in the ledger and survives replay.
- Revoking a grant cascades to all its leases within the same transaction.
- Expiry is **evaluated**, never stored as a state field: `is_expired(now)`. A state field would go stale between writes and could report an expired grant as valid.
- Revocation is terminal and irreversible. Re-authorization requires a new grant with a new `PolicyDecision`.

### `now` injection
All time-dependent checks take an explicit `now` parameter. No capability code calls `time.time()` internally. This makes expiry deterministically testable and makes replay independent of wall-clock drift.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Extend `CapabilityRegistry` | Different concept (possession vs authorization), different lifecycle, and it is mutated through a shared connection by five subsystems — adopting it would defeat ADR-0103. Rejected; term mapping recorded instead. |
| Single-phase consumption (record use after the effect) | Exactly the crash window Finding E identifies. A crash after the effect leaves the use unrecorded and the budget wrong in the unsafe direction. Rejected. |
| Increment usage at finalize instead of reserve | Fails open: a crash after the effect leaves budget available for a repeat. Reserve-first fails closed. Rejected. |
| Check revocation only at work-order issue | Precisely Finding D. Rejected. |
| Store `expired: bool` | Goes stale; a read between writes can report a wrong answer. Rejected in favour of evaluation. |
| Allow retry of `indeterminate` | Can duplicate an external side effect. Forbidden by invariant 12. Rejected. |
| Allow un-revocation | Would make revocation non-terminal and the audit trail ambiguous. Rejected. |

## Consequences

**Positive**
- Authority cannot outlive its revocation, even mid-run.
- Every consequential use has a reservation and a consumption record — a complete audit chain.
- Crash windows fail closed in every case.
- Expiry and revocation are deterministically testable.

**Negative / costs**
- A crash between reserve and effect burns a use that never happened. This is the deliberate fail-closed trade; the reservation remains `open` and visible for reconciliation.
- Two-phase adds a round trip per consequential operation.
- Callers must thread `now` explicitly.

## Reversal conditions

1. Burned-use-on-crash proves operationally unacceptable → introduce reservation expiry with automatic release, which requires proving the release cannot race a slow-but-successful effect (new ADR).
2. Delegation chains deeper than lease→grant are required → extend with an explicit narrowing-only delegation chain and prove monotone narrowing at every hop.

## Evidence from the current repository

- `capt_solo/foundry/registry.py:57-74` — `Capability` dataclass: no subject, resource, scope, operations, grant, lease, or validity window.
- `capt_solo/foundry/registry.py:348` — `revoke()` sets a lifecycle string on the catalogue entry; it is not an authorization revocation and produces no event.
- `capt_solo/foundry/registry.py:292` — `set_degraded()` mutates state directly on the shared connection.
- No lease, reservation, or consumption concept exists anywhere in the tree (`grep -rni "lease\|reservation" capt_solo/` → 0 relevant hits).
