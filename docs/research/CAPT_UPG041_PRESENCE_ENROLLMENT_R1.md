# CAPT-UPG-041 R1 — Operator Presence, Enrollment, and Challenge Prototype

**Date:** 2026-10-19 (CDT), worktree `feat/upg041-presence-signing-r1`.
**Baseline:** experimental R4 `6768cc687d201c93023e11ce69bc948139c2ebe7`.
**Status:** experimental / disabled for production; no real operator enrollment performed.

## The implemented vertical slice

### macOS native CAPT application

`Sources/CAPTCoreDesktop/CAPTSecureEnclavePresence.swift` defines an explicitly invoked
Secure Enclave P-256 private-key generator with `kSecAttrTokenIDSecureEnclave`,
`kSecAttrAccessibleWhenUnlockedThisDeviceOnly` and access-control flags
`[.privateKeyUsage, .biometryCurrentSet]`. It checks availability of biometric
authentication, refuses to overwrite an existing key tag, and fails closed if the
created key does not report the Secure Enclave token.

A signing call retrieves the protected key using `LAContext` with zero allowed
biometric reuse, validates the exact R4 issuance challenge shape and 60-second
window, and signs `CAPT:DecisionOfferingIssuerProof:v1\\0 || canonical_json`
with `ecdsaSignatureMessageX962SHA256`.

The public key is exported in standard SubjectPublicKeyInfo PEM form. **Only the
public key is exported**. The private key remains non-exportable by the Security
API contract. The app does not insert a key into the CAPT RuntimeService registry.

`CAPTNativeMac/Views/CAPTPresenceEnrollmentView.swift` is accessible in the
Settings screen. It has an explicit **Create Secure Enclave key** button, labels
the resulting public key **unregistered**, provides a copy-PEM action, and
states that no permissions or issuer credentials have been granted.
Nothing executes at app startup. A user pressing the button on a signed app
would create a local key subject to device availability and OS policy; no
programmatic UI press or biometric operation was performed in this mission.

Swift tests use only ephemeral **software** P-256 keys for PEM interoperability,
and known fixed canonical JSON inputs. They do not enroll a hardware key.
Swift package compilation is not proof that a signed, deployed application
can perform Secure Enclave enrollment.

### Root-signed enrollment and one-time challenge prototype

`research/quantum_leap_r4/issuer_challenge_store.py` provides an isolated
SQLite proof-of-concept, **not a production RuntimeService endpoint**.
It requires two real CAPT EventStore instances at construction and refuses to
reuse either store path/inode for its challenge ledger. It records the supplied
enrollment-root PEM digest, and refuses a different root on reopening.

Enrollment requires a P-256 certificate signature by the externally supplied
enrollment root over exactly:
`{schemaVersion, issuerId, keyId, publicKeyPEM, purpose}`.
There is no unauthenticated self-registration. A separate root-signed action
revokes an issuer key without deleting its audit identity.

A challenge is created only for a non-revoked enrolled key, with a 256-bit random
nonce, exact command/request fingerprints, two current EventStore chain digests,
a 60-second UTC window, and fixed issuance purpose. It is stored before being
returned. The R4 ECDSA verifier checks the submitted signature against the
**stored** challenge and registered key. An isolated `BEGIN IMMEDIATE` SQLite
transaction atomically consumes the nonce. A consumed nonce cannot be used again,
including from a second connection. A changed CAPT main/sidecar ledger head
causes refusal.

A successful result explicitly remains:
`SIGNED_CHALLENGE_CONSUMED_NOT_AUTHORIZATION`, with
`operatorPresenceVerified=false`, `rootCustodyIndependentlyVerified=false`,
`runtimeAdmissionVerified=false`, `dispatchAllowed=false`, and
`completionVerified=false`.

## Independent acceptance evidence

- macOS Swift build and 11 dedicated tests: canonical signing bytes match
  the pinned Python R4 verifier SHA-256, malformed challenges fail, and standard
  P-256 public-key PEM serialization works using software test keys.
- Python research tests: actual temporary SQLite and real CAPT EventStore
  instances, genuine P-256 ECDSA signatures and root-signed enrollment certificates.
  Cases include root impersonation, key revocation, expiry, replay on two connections,
  wrong ledger, stale main-world event, same-database reuse denial, and changed
  ledger-object refusal.
- No live CAPT provider, paid model, HumanApproval, production EventStore,
  deployment, account credential or installed runtime was touched.

## Critical unclosed gates

1. **Trusted enrollment authority custody.** The prototype accepts the root
   public key as a constructor argument and stores its hash in a same-UID
   SQLite file. This is not proof that it came from an independent authority.
   Real deployment must pin keys and rotation/revocation through a protected,
   audited ceremony outside model-writable roots.
2. **Operator presence provenance.** An ECDSA signature alone cannot show
   whether its private key was hardware-backed or Touch ID was used. A signed
   binary's Security API contract is distinct from an independently attested
   key-enrollment record. Signer attestation and signed app identity require
   separate review.
3. **No live RuntimeService API integration.** The prototype's challenge issuer
   is not wired into the real authenticated RuntimeService transport and
   still accepts caller-supplied intended request IDs/digests. Production must
   derive these from authenticated current request state.
4. **Transaction topology.** Challenge nonce consumption is atomic in its own
   SQLite ledger, but not in a distributed transaction with both CAPT
   EventStores, ToolBroker admission, or external-world effects. The two head
   checks can race with an external writer. Do not treat them as execution proof.
5. **Key lifecycle.** Enrollment certificate has no expiry, root rotation
   ceremony and operator recovery are unimplemented, and rollback/versioning
   for the prototype registry need design.
6. **OS enrollment test.** Do not claim actual Secure Enclave success until an
   operator taps the app button, confirms the system biometric prompt on the
   signed app, and an independently verified proof and key record are observed.
7. **No silent downgrade.** If Touch ID/Secure Enclave is unavailable,
   refuse, not auto-fallback to a software key or a human-tagged session token.

## Promotion criteria

Build an authenticated CAPT RuntimeService enrollment/challenge endpoint that
only mints challenges from registered request objects; have a protected
enrollment authority sign the Secure Enclave public key/operator binding; verify
the signed challenge against enrolled/current keys, consume the nonce as part
of the consequential authority transaction, recheck grant/lease/policy before
ToolBroker admission, and require independently custodied outcome readback
before completion. Prove revoked key, biometric-reset, nonce replay,
client-disconnect, service-restart, same-UID and rollback cases.

**Release decision: HOLD.** The tested code is a useful foundation, not yet
trusted operator presence or deployable autonomous execution authority.
