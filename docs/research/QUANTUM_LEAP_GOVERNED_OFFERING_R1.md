# Quantum Leap — Governed Decision-Offering Receipts (R1)

**Date:** 2026-10-19
**Source baseline:** CAPT Core origin/main 2ce53288f565cd387a1d7629b41690f9872b2a4b
**Branch:** experiment/quantum-leap-governed-offerings-r1
**Status:** gated implementation candidate; not installed in the deployed runtime

## Thesis and scope

A typed model proposal must not become an execution capability merely because it
has a digest or a high probability. A governance-authorized CAPT runtime should
produce a short-lived, durable receipt binding the *exact* intended ToolRequest,
registered tool descriptor, actor recorded in runtime metadata, and local ledger
basis. A revocation must be durable and inspectable.

This implementation provides that issuance, revocation and inspection using
the actual CAPT RuntimeService/EventStore and ToolBroker internals. It does not
alter ToolBroker.execute, does not cause an adapter dispatch, does not consume
HumanApproval, and does not declare task completion.

## Actual implementation

- New event types: DecisionOfferingIssued, DecisionOfferingRevoked.
- New closed contract definitions: DecisionOfferingReceipt and DecisionOfferingState.
- New EventStore stream namespace: decision_offering.
- New authoritative acts: issue_decision_offering (governance_kernel only);
  revoke_decision_offering (governance_kernel or human).
- The ToolBroker's new issue/revoke/inspect methods call GovernedDecisionOfferingService.
- Issuance validates the real ToolRequest, its semantic fingerprint, the
  currently registered descriptor, its readiness and, when supplied, the
  current capability lease. Governance command identity is separately bound
  to exact request, TTL, issuer and descriptor digest.
- Receipt includes the complete ToolRequest digest (not just the semantic
  request fingerprint), a 256-bit randomly generated nonce, a digest of all
  immutable receipt fields, issuer identity from CommandMetadata, expiry,
  descriptor identity and the current ledger chain digest.
- EventStore atomically commits aggregate version, event, chain and idempotency
  record. Repeated identical issuance/revocation commands are idempotent.
- Revocation changes the authoritative aggregate and emits a second event.
- Inspection revalidates the persisted receipt, exact ToolRequest and live
  descriptor, expiry and revocation state, and rejects even an unrelated
  intervening ledger event (deliberately conservative v1 behavior).
- Every inspection result always has dispatchAllowed=false and
  completionVerified=false; externalWorldVerified=false and
  humanPresenceVerified=false.

## Evidence and negative controls

The tests use real EventStore SQLite persistence and the existing actual
FileToolAdapter and ToolBroker. No fake RuntimeService or fake adapter is
used. Tests cover durable write/restart/replay, real contract validation,
expiring TTL, revocation, unauthorized actor kinds, descriptor drift,
exact request/ID substitution, ledger advancement, receipt tampering, and
the distinction between ledger state and an independently modified file.

The positive inspection is deliberately named as an identity-current,
not-dispatchable finding. An external file can change without an EventStore
event: the inspection does not detect that outside change, and therefore
does not claim external world verification.

Commands checked:
- python3 contracts/tools/check_drift.py
- python3 -m pytest -q tests/capt_runtime/test_decision_offering_receipts.py
- python3 -m pytest -q tests/capt_runtime/test_contracts.py
- Selected CAPT broker/authority/contract/world-receipt/ledger regressions.

At authoring time: 140/140 selected regressions passed, including generated
Python/TypeScript contract parity. This is not a claim that the full CAPT
suite, active desktop app, production runtime or provider integration passed.

## Serious limitations and merge blockers

1. **No physical human attestation.** The metadata actor kind inherits CAPT's
   existing authenticated caller/token-holder trust model. Naming it 'human'
   does not prove human presence or Secure Enclave consent.
2. **No independent oracle custody.** The event ledger, issuer and recipient
   may operate under the same-UID machine. This is not an independently
   attested evaluator or a verified external target state.
3. **Only CAPT-ledger freshness.** The receipt records the ledger chain at
   construction, not a serializable, independently observed target snapshot.
   The head-sequence check invalidates an offering on *any* later CAPT event;
   under concurrent issuing, the receipt's ledger-basis value is not an
   atomic preimage. Correct CAS/observation custody remains necessary.
4. **No production execution gate.** The new inspect method is available
   internally but ToolBroker.execute does NOT require a receipt. This must
   not be described as production enforcement. ToolBroker's existing
   authority, reservation, dispatch, settlement and reconciliation still
   govern execution.
5. **Schema version compatibility.** New closed event/stream definitions
   change the normative source digest without changing schemaVersion 1.0.0.
   A migration/version-negotiation plan is required before shipping, with
   mixed-version read/write and rollback tests.
6. **Narrow-scope TTL.** The current 1–300 second TTL is deliberate, while
   invalidation on any intervening ledger event is safe but may be too
   noisy to use in a busy runtime. Optimize only after adversarial tests.
7. **Tool schema is not the decision probability model.** R1 binds exact
   ToolRequest and registered descriptor, not complete model distributions,
   secure model identity or calibrated uncertainty.
8. **External library/license boundary.** This code was authored within
   CAPT and does not copy System One Harness source. CAPT's new
   Cognitive Sovereignty License embeds CC BY-SA 4.0 plus additional terms.
   That combination needs specialist licensing review prior to distribution
   or importing third-party copyrighted code.

## Next acceptance gates

- A custody-isolated source/target oracle with signed readback, target version
  and current-world revalidation.
- Independent source-attestation of policy/observation and nonce issuance,
  with real revocation detection at actual ToolBroker admission.
- Current grant, lease, registry and privilege checks in the one transaction
  that moves from proposal to dispatched effect; no TOCTOU gap.
- A governed operation-specific postcondition verifier separate from provider,
  model output and adapter self-report. No 'finish' or matching receipt alone.
- Full-suite, schema migration and mixed-version compatibility checks.
- Independent semantic adjudication of v3 content claims remains open; this
  implementation does not close the 52-claim review register.

**Operational boundary:** No running CAPT service, deployed runtime, provider,
human approval, CCF+ promotion, or release gate was modified by this work.

## R2 evidence update (2026-10-19)

Follow-up: [R2 issuance hardening and compatibility gates](QUANTUM_LEAP_GOVERNED_OFFERING_R2_GATES.md). The R2 experiment binds the issuance ledger predecessor inside the SQLite commit transaction and disables the new interface by default. Mixed-version readers still reject the new event format; this remains a draft, not production enablement.
