# CAPT Solo v0.4 — Capability Registry

The Capability Registry is the single source of truth for "can CAPT do X?".
Every capability is registered with explicit evidence, trust, lifecycle, and
degradation state. ClaimGuard queries it before any completion claim.

## Lifecycle

```
candidate -> validated -> proven -> verified -> degraded / revoked / deprecated
                                  -> experimental
```

Three DISTINCT events advance epistemic status (each idempotent):

1. `verify()` — candidate/experimental → validated (proof requirements satisfied).
2. `mark_proven()` — validated → proven (proof still satisfied).
3. `govern_approve(approver=, ctp_tx_id=)` — proven → verified (explicit
   governance approval with named approver + CTP receipt).

Calling `verify()` twice does NOT skip to `proven`. Calling `govern_approve()`
on an already-verified capability is a no-op.

## Degradation

12 explicit reason codes (`DEGRADATION_REASONS`): `dependency_missing,
environment_changed, proof_expired, compatibility_failed, security_revoked,
manual_disable, superseded, verification_failed, component_degraded,
tool_contract_changed, permission_policy_changed, artifact_missing`.

`degrade(reason, explanation=, affected_scope=, triggering_evidence=, actor=,
remediation=, ctp_tx_id=)` records a structured degradation record (reason,
explanation, scope, evidence, previous/resulting state, timestamp, actor,
remediation, CTP receipt) in `capability_degradations`. `security_revoked`
moves the capability to `revoked`; all others to `degraded`. `get_degradations()`
retrieves the history.

## Implemented

- Full lifecycle with 3 distinct, idempotent advancement events.
- 12 degradation reason codes with structured records.
- Trust scoring from proof aggregate.
- `query(claim)` lookup by identifier/description for ClaimGuard.

## Experimental

- Automated re-verification on environment change.

## Future

- Capability composition (a capability composed of sub-capabilities).
- Cross-capability conflict detection.

## Limitations

- Trust is operator-assigned via proof evidence, not derived from runtime.
- Degradation is recorded but does not auto-remediate.

## Security Boundaries

- A capability is NEVER reported as verified without a satisfied proof
  aggregate.
- Degraded/revoked capabilities are downgraded in all claims.
- `govern_approve` requires a named approver; anonymous approval is rejected.

## Verification

- `tests/test_v04_foundry.py` (registry lifecycle, verify/prove/approve).
- `tests/test_v04_degradation.py` (12 codes, structured records, scoped language).
- `verify_runtime.py` (capability_verify, degradation_reasons).
