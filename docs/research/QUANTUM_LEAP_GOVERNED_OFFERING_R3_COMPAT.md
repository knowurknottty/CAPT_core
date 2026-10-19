# Quantum Leap R3 — Legacy-compatible isolated offering ledger

**Date:** 2026-10-19
**Implementation branch:** `experiment/quantum-leap-governed-offerings-r1`
**Compatibility baseline:** `3ff7caee5fc89f33d90b3754d6dc518d4e914559`
**Status:** Research / draft PR #242; no production activation.

## Root cause and fix

CAPT Core's original `1.0.0` generated validator has a closed event-type union and closed stream prefixes. New `DecisionOfferingIssued` and `DecisionOfferingRevoked` are rejected by any pre-extension validator if inserted into the *main* EventStore ledger. Renaming the version cannot make already-running old code recognize unknown event shapes.

R3 keeps these events entirely out of the main EventStore:

- `ToolBroker` defaults to `governed_offerings_enabled=False`.
- Explicit experimental opt-in requires a *separately supplied EventStore* for decision offerings. Main-ledger object identity and matching filesystem/inode identity are refused.
- `GovernedDecisionOfferingService` owns the separate ledger for issuance, revocation, immutable event history and idempotency. The main runtime remains responsible for current tool descriptor and capability lease validation.
- The receipt contains two separate digests: `ledgerBasisDigest` for the **main CAPT ledger** and `offeringLedgerBasisDigest` for the **isolated offering ledger**.
- The offering-ledger predecessor is compared *inside that ledger's SQLite write transaction*; main-ledger identity is checked before and after issuance and on later inspection.
- A sidecar-local `decision_offering_contract` manifest pins the **exact generated source digest**, refusing a changed sidecar schema until an explicit migration. Only a validated issuance initializes this manifest; inspection and revocation validate it read-only. The manifest does not modify the main CAPT ledger.
- Every result remains `dispatchAllowed=false`, `externalWorldVerified=false`, `humanPresenceVerified=false`, `completionVerified=false`.

## Observed backwards-compatibility result

A real `TaskTransitioned` legacy fixture event was appended to a main EventStore. A real `DecisionOfferingIssued` event was issued concurrently in a physically separate SQLite sidecar. The generated Python contract reader extracted from pinned `3ff7caee` **accepted the real legacy main event** and **rejected the sidecar-only offering event**. The latter rejection is expected and harmless because legacy main-ledger readers are never directed to the sidecar by the managed CAPT interface.

The new offering reader accepted its sidecar event and preserved revocation/idempotency/expiration behavior. The test additionally confirms no offering stream appeared in main. The sidecar is not a legacy-compatible database on its own; it is deliberately a distinct format and must be opened only by a source-digest-matched extension-aware reader.

## Evidence limits and remaining blockers

**This fixes main-ledger *format exposure*, not all multi-version operational compatibility.** Across the two stores there is no atomic distributed transaction or independently custodied world snapshot. A main-ledger change mid-issuance causes a fail-closed error, but the sidecar audit event may already have been committed. A change after receipt issuance causes inspection refusal. An external target change not logged in the main CAPT ledger still cannot be proven or detected.

Sidecar schema migration remains necessary whenever its generated source digest changes. This policy intentionally fails closed rather than silently upgrading a sidecar. The new events are still declared within the broad generated `1.0.0` contract source; future schema versioning and negotiation need separate review for shared contract publishing.

Issuer authentication remains inherited from existing CAPT CommandMetadata actor-kind checks, not verified Secure Enclave human presence. A same-UID adversary with control of the writer and checker is outside the current custody guarantees. No automatic gate was added to ToolBroker dispatch, no independent outcome readback is present, and CCF+ stays closed.

**Do not merge or enable** until runtime issuer custody, full-suite acceptance, mixed-instance deployment isolation, sidecar migration/rollback, and independent world-postcondition verification are reviewed.

## Tests

- `tests/capt_runtime/test_decision_offering_receipts.py` includes real SQLite main+sidecar histories, old-reader subprocess validation, main-store reuse refusal, sidecar manifest source-digest refusal, main-ledger drift invalidation and receipt lifecycle tests.
- Contract bindings were regenerated from authoritative schemas; schema drift and Python/TypeScript parity must pass before commit.
- No provider calls, actual human approvals, production ledger mutations, deployment or runtime restart were authorized or performed.
