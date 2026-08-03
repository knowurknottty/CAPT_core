# ADR-0110 — Trusted CAPT state versus untrusted external observations

**Status:** Accepted (M0-A)
**Date:** 2026-08-02
**Relates to:** spec §10.1, invariants 9 and 25, ledger Finding H, workflow Gate 3

## Context

Spec invariant 9: drivers are untrusted integration components, not CAPT authorities. Ledger Finding H: an external harness could otherwise forge `TaskCompleted`, `EvidenceRecorded`, or similar CAPT outcomes.

M0-A integrates no driver. But the *type system and validation boundary* must be established now, because retrofitting a trust boundary after code paths exist is how trust boundaries get bypassed. If the untrusted types are added later, the first driver integration will naturally reuse the authoritative types and the distinction will be lost.

## Decision

**Two disjoint type families, structurally incapable of substitution, with a validating conversion as the only path between them.**

### Family A — Authoritative CAPT records
`EventEnvelope`, `ClaimRecord`, `EvidenceRecord`, `VerificationResult`, `ClaimGuardDecision`, `CapabilityGrant`, `CapabilityLease`, `CheckpointManifest`.

Only the CAPT runtime constructs these. Every one carries `eventId`/record id, `schemaVersion`, and — for events — `streamId`, `streamVersion`, `correlationId`, `causationId`, `payloadDigest`.

### Family B — Untrusted external candidates
`DriverObservation`, `DriverArtifactCandidate`, `DriverReceiptCandidate`, `DriverClaimProposal`, `DriverProgressSignal`.

Every Family B type carries a **mandatory** `trust: "untrusted"` field (`const` in schema, `Literal` in Python, string-literal type in TypeScript) and a mandatory `observedBy: <driverId>` field.

### Structural non-substitutability

1. **No shared parent type.** Family B does not inherit from, embed, or alias any Family A type.
2. **`trust: const "untrusted"`** cannot be omitted or set to any other value; schema validation rejects it. There is no `trust: "trusted"` variant of a driver type — the value space has exactly one member.
3. **Family B has no `streamId`, no `streamVersion`, no `eventType`.** A driver payload is therefore structurally incapable of being appended to the ledger: `RuntimeStore.append()` requires those fields and rejects anything else.
4. **Event-type registry check.** `RuntimeStore.append()` validates `eventType` against the generated `EventType` enum and against `EVENT_TYPE_OWNER` (ADR-0103). A driver-supplied event type name is not in either and is rejected with `UnknownEventTypeError`.

### The only conversion path

```
DriverObservation (untrusted)
   → CAPT validation: schema, driver identity, lease binding,
     work-order correlation, content policy
   → CAPT constructs EvidenceRecord (authoritative)
   → EvidenceRecorded event appended by the CAPT runtime
```

The conversion is a CAPT-owned function. It never copies a driver-supplied id into an authoritative id field; CAPT mints fresh identifiers and records the driver-supplied ones as *attributes* (`sourceObservationId`, `observedBy`) so provenance is preserved without authority transfer.

### Claim proposals are never claims

`DriverClaimProposal` cannot become a `ClaimRecord` with `verificationStatus: verified`. A proposal enters as `unverified` and can only be promoted by an independent `VerificationResult` produced by CAPT's verification pipeline. A conformance test asserts that no code path constructs a verified `ClaimRecord` directly from a proposal.

### M0-A scope

M0-A defines the contracts, the validation boundary, and the negative tests. It integrates **no** driver and defines **no** `DriverHost`. `DriverRunAggregate` exists as a state model with no external I/O. This is stated explicitly so the presence of driver contracts is not mistaken for driver capability.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| One type family with a `trusted: bool` flag | A boolean is one assignment away from being wrong; a forgotten default or a copied struct silently grants authority. Structural separation cannot be undone by an assignment. Rejected. |
| Runtime-only checks, shared types | Requires every call site to remember the check. The failure mode is silent. Rejected. |
| Sign driver output | Proves *who* sent it, not that it is *authoritative*. A signed forged completion claim is still a forged completion claim. Orthogonal; deferred. |
| Defer untrusted types to M0-B | Guarantees the first driver integration reuses authoritative types and the boundary is lost before it exists. Rejected. |
| Allow drivers to propose event types validated against an allowlist | An allowlist is a shared-namespace design; a mistake in the list grants authority. Drivers emit no event types at all. Rejected. |

## Consequences

**Positive**
- A driver cannot forge an authoritative event, even with a malicious or buggy implementation — the type lacks the required fields and the event type is unknown to the registry.
- Provenance is preserved through conversion without authority transfer.
- The boundary exists before the first driver, so it cannot be retrofitted around.

**Negative / costs**
- Duplicate-looking types (`DriverArtifactCandidate` vs `EvidenceRecord`). This duplication is the point; a comment in each schema states so, to prevent a future refactor from "simplifying" them into one.
- Conversion code must be written and maintained per candidate type.
- Slightly larger contract surface in M0-A than strictly needed for the state proof.

## Reversal conditions

1. If the two families are ever unified "for convenience", this ADR is violated and M0-A's authority evidence is void. Unification requires a new ADR with an argued threat model.
2. If a driver is ever granted the ability to name an event type, the registry check must be replaced with a proven-safe mechanism and re-tested.

## Evidence from the current repository

- `capt_solo/foundry/harness.py:183` `_execution` — the existing skill-validation harness runs in-process and its output feeds `ProofEngine` evidence directly. There is currently **no** trust boundary between an executor's self-report and recorded evidence. This is the exact confusion the new boundary prevents.
- `capt_solo/foundry/proof.py:136` `record()` — accepts caller-supplied evidence with no notion of trusted vs untrusted origin.
- `capt_solo/foundry/claimguard.py:79` `verify_claim(text)` — operates on natural-language text; nothing structurally prevents an executor's prose from being treated as a claim.
- No driver, driver host, or external execution boundary exists in the tree.
