# CAPT-UPG-015 — Live Capability Lease Inspector + Governed Revoke/Kill

- **Campaign ID:** `CAPT-UPG-015`
- **Issue:** #81
- **Base:** verified CAPT-UPG-014 @ `7b62f529a007fc52012d37aab8eb585206e4cf00`
- **Disposition:** `IMPLEMENTED_VERIFIED_READY_FOR_OWNER_REVIEW`

## Delivered

### Read-only lease inspector

`capt_ui.operator.leases` projects authoritative Capability aggregate state into an operator-facing lease view containing grant/lease identity, scope, operations, validity window, usage ceilings, consumption, open reservations, reconciliation-required reservations, and revocation state.

The projection is explicitly `projection_only`; it does not expire, revoke, widen, or otherwise mutate authority.

### Governed revoke / kill-key

The control path is:

`authenticated operator command`
→ `LeaseRuntimeCommandService`
→ base `RuntimeService.revoke()`
→ exact grant/lease target binding
→ `CapabilityAggregate.revoke()`
→ durable `CapabilityGrantRevoked` / `CapabilityLeaseRevoked` event
→ immediate failure of subsequent `check_lease()` calls.

Important authority properties:

- operator identity/session binding is enforced at the authenticated command relay;
- UI supplies explicit grant ID, target kind, exact target ID, and reason;
- target binding is enforced in **base RuntimeService**, not a UI helper or composition-only subclass;
- a grant revocation must name that grant;
- a lease revocation must name the currently recorded lease;
- revocation remains terminal and irreversible in CapabilityAggregate;
- exact command replay is idempotent;
- same idempotency key with changed semantics is rejected;
- revocation never manufactures replacement authority;
- the runtime advertises `revoke_capability` in its command capability projection.

### Operator surface

`LeaseEpistemicCaptTUI` extends the claim-scoped epistemic TUI with:

- live lease projection;
- explicit grant/lease targeting fields;
- required revocation reason;
- governed REVOKE/KILL action;
- no direct capability-state mutation.

`capt-tui` points to this lease-aware epistemic surface.

## Verification

Focused pre-commit gate on corrected ancestry:

```text
15 passed
lease_tui_import=PASS LeaseEpistemicCaptTUI
```

The focused tests prove authenticated revoke, idempotency, conflict rejection, wrong-identity rejection, target mismatch rejection at base RuntimeService, durable restart state, post-revocation lease denial, projection semantics, command discoverability, and preservation of epistemic UI behavior.

Exact-commit contract drift and full non-slow pytest verification are recorded on the CAPT-UPG-015 PR after this commit is created. Tests marked `slow` remain outside the repository's default pytest gate.
