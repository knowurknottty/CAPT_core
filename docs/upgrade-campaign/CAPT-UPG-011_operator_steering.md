# CAPT-UPG-011 — Governed Out-of-Band Operator Steering

- **Campaign ID:** `CAPT-UPG-011`
- **Issue:** #71
- **PR:** #72
- **Base:** `upgrade/capt-upg-010-cohort-persistence` @ `b982d544f26e7f951be3928eeb5c9fb9b1587123`
- **Disposition:** `IMPLEMENTED_VERIFIED_READY_FOR_OWNER_REVIEW`

## Authoritative path

The earlier receipt-only command was rejected because it did not mutate durable Cohort state. The corrected path is:

`authenticated operator command`
→ composition-owned command relay
→ `SteeredRuntimeService`
→ `CohortAggregate.steer()`
→ durable `CohortSteered` EventStore event
→ epoch increment / prior-contribution staleness
→ restart reconstruction through Cohort replay.

Properties:

- only a human actor may author `steer_cohort`;
- directive, reason, actor, timestamp, and resulting epoch persist in `latestSteer`;
- exact retry is idempotent;
- changed semantics under the same idempotency key are rejected;
- earlier contributions remain durable evidence but cannot satisfy current-epoch quorum;
- steering does not create, widen, revoke, or otherwise mutate a capability lease;
- capability expansion remains a separate governed authorization transaction.

## Contract + operator discovery closure

UPG-011 extends the already-durable Cohort contract with:

- `CohortSteered` in the closed `EventType` set;
- a typed `CohortSteeredPayload` carrying the durable `CohortSteer` record;
- a cross-language valid steering EventEnvelope fixture;
- `steer_deliberation` in the runtime-advertised command capability set.

The runtime server constructs the command relay through `RuntimeComposition.command_service()`; the stale direct `RuntimeCommandService` import was removed.

## Verification

Focused pre-commit gate:

```text
DRIFT CHECK: OK (11 generated files match the schema source)
30 passed
```

Exact-commit full-suite verification is recorded on PR #72 after commit creation. The suite excludes tests marked `slow` by repository pytest configuration.
