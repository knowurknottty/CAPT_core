# CAPT Solo v0.4 — ClaimGuard

ClaimGuard is the gatekeeper that prevents unsupported completion claims. It
queries the Capability Registry (and Proof Engine) before asserting "CAPT can
do X" or "Task complete and verified."

## Behavior

- `ClaimGuard.verify_claim(text, capability_id=)` — scans `text` for claim
  trigger verbs (complete, fixed, migrated, production-ready, tested, secure,
  verified, successful). If a capability is referenced and its lifecycle is
  `verified` with satisfied proof, the claim is supported. Otherwise the claim
  is downgraded with explicit language — never reported as verified.
- `ClaimGuard.assert_capability(identifier)` — explicit "can CAPT do X?"
  query. Returns supported only if the capability is `verified`.

## Degradation-aware language

When a capability is `degraded`, ClaimGuard reads the latest structured
degradation record and produces **scoped** language:

- A capability degraded ONLY on `macos` is reported as "degraded on macos only
  (reason: compatibility_failed); not globally revoked".
- A globally degraded capability is reported as "degraded (reason: manual_disable)".

This prevents a platform-specific degradation from being misreported as a
global revoke.

## Implemented

- Trigger-word detection with downgrade template.
- Registry-proof linkage (never asserts verified without satisfied aggregate).
- Scoped degradation language by reason + affected_scope.
- `assert_capability` explicit query.

## Experimental

- Natural-language claim parsing beyond fixed trigger verbs.

## Future

- Multi-capability claim decomposition.
- Confidence-scored claims.

## Limitations

- ClaimGuard does not infer intent, diagnosis, or psychological state.
- It operates on registered capabilities only; unregistered claims are
  reported as unsupported.

## Security Boundaries

- Never reports a capability as verified unless the ProofEngine aggregate is
  satisfied AND lifecycle is `verified`.
- Degraded/revoked capabilities are always downgraded, never upgraded.
- No claim is auto-generated; ClaimGuard only validates user/agent claims.

## Verification

- `tests/test_v04_foundry.py` (claim validation, downgrade language).
- `tests/test_v04_degradation.py` (scoped degradation language).
- `verify_runtime.py` (claimguard_verified).
