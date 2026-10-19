# Quantum Leap R4 — P-256 issuer-signature verification (research only)

**Source baseline:** CAPT Core Quantum Leap R3 `e0dc28cd48bed19fe8c71520c2bba15a27fa7572`
**Date:** 2026-10-19
**Upstream design:** CAPT-UPG-041 Human Presence Attestation, in `docs/upgrade-campaign/CAPT-UPG-025-068_SAME_UID_HARDENING_AND_EVOLUTION.md`

## What is implemented

`research/quantum_leap_r4/issuer_signature.py` is a **pure verification primitive**, not a signer or issuer. It validates a domain-separated ECDSA P-256 / SHA-256 DER signature against a public key supplied by a presumed trusted enrollment registry.

Its strictly shaped, canonical JSON challenge binds:

- `requestId`, `issuerId`, `keyId`, and fixed `action=issue_decision_offering`;
- `commandFingerprint` and the exact `toolRequestDigest`;
- `mainLedgerDigest` and isolated `offeringLedgerDigest`;
- 256-bit nonce plus UTC `issuedAt`/`expiresAt` (maximum 60 seconds);
- `schemaVersion=capt.decision-offering-issuer-proof.v1`.

An independent caller-supplied expected challenge is compared **exactly** before verification, preventing a correct signature for a different request from satisfying this particular proposed intent.

Public keys are never accepted from the signature envelope. The externally supplied registry must match the key ID, issuer identity, P-256 curve, non-revoked state and purpose `decision_offering_issue`. Other curves, malformed signatures and invalid challenge structure are rejected.

## What signature validation does *not* establish

Even when the ECDSA signature is mathematically correct, the result is `SIGNATURE_VALID_BUT_NOT_AUTHORIZATION`.

The result **always** reports:

- `enrollment_custody_verified=false`
- `operator_presence_verified=false`
- `nonce_consumption_verified=false`
- `capability_verified=false`
- `dispatch_allowed=false`
- `completion_verified=false`

This is intentional: the supplied public-key registry is not yet independently authenticated; the verification clock is not guaranteed to come from a protected runtime; repeat signatures remain cryptographically valid until the system atomically consumes a nonce. There is **no Secure Enclave integration**, code-signature check, enrollment UI, stored private key, HumanApproval modification, real issuing runtime, or provider call.

**A software-generated P-256 signature is not evidence of Touch ID or human presence.** The test keys are ephemeral, generated in the test process, and never installed or written as credentials.

## Required integration before issuer authentication can be claimed

1. **Enrolled operator signer:** signed macOS app generates non-exportable Secure Enclave P-256 key with a LocalAuthentication-protected private-key use policy. Enrollment pins the public key and operator identity through an independently reviewed ceremony. The currently implemented Keychain AES-GCM state key is *not* a substitute for Secure Enclave signing.
2. **Trusted key registry:** RuntimeService reads independently protected enrollment records, including purpose, device/app identity, key IDs, rotation and revocation. Same-UID writable registry/configuration must be considered attacker-controlled.
3. **Runtime-issued challenge:** RuntimeService mints the challenge, the clock and unpredictable nonce and snapshots current policy + exact ToolRequest and separate ledger digests. A model or connector cannot supply replacement expected fields.
4. **Signing prompt:** use the system-owned LocalAuthentication flow for operator consent, with explicit risk-tier batching and no silent headless downgrade.
5. **Atomic nonce/revocation gate:** after signature and protected provenance validation, atomically consume nonce, enforce user/operator scope and live revocation, and bind the authorization to the exact issuance transaction.
6. **Current authority:** ToolBroker still verifies tool registry, capability and lease at admission. This signature does not authorize dispatch or certify effects.
7. **Independent postconditions:** externally custodied target readback and outcome tests are separate from approval identity.

## Threat model and negative controls

The accompanying suite uses real in-memory ECDSA P-256 signatures; **22 tests pass**, including unknown/revoked keys, identity/key-purpose substitution, wrong P-256 signer, P-384 enrollment, modified request/ledger digests, expiry, noncanonical time, excessive TTL, cross-purpose signing, injected untrusted public key, malformed base64, replay and unauthenticated clock.

No release-signing or user key is generated or used. No signing operation exists in production code.

## Rollout recommendation

Keep as **research-only behind the R3 experimental branch**. Do not mark R3/R4 production-ready, merge the parent PR #242, or relax its default-off gate based on these tests. Shipping requires real Secure Enclave-backed enrollment, verified signer custody, nonce replay prevention and negative same-UID tests. Linux/headless operation needs an explicit, clearly weaker policy path, not a silent fallback.
