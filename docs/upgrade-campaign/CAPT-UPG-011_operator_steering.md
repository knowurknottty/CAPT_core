# CAPT-UPG-011 — Governed Out-of-Band Operator Steering

- **Campaign ID:** `CAPT-UPG-011`
- **Issue:** #71
- **PR:** #72
- **Rebuilt Base:** `upgrade/capt-upg-010-cohort-persistence` @ `eadef49e5ba602e27dc3f4a674688550e6d0f511`
- **Status:** `IMPLEMENTED_PENDING_EXACT_HEAD_TEST`

## Corrected implementation

The earlier receipt-only command was rejected by owner audit because it did not mutate authoritative Cohort state. The corrected path is:

`authenticated operator command`
→ `GovernedRuntimeCommandService`
→ composition-owned `SteeredRuntimeService`
→ `CohortAggregate.steer()`
→ durable `CohortSteered` EventStore event
→ epoch increment / prior contribution staleness
→ restart reconstruction through the existing Cohort replay reducer.

Key properties:

- only a human actor may author `steer_cohort`;
- the steering directive is durable in `latestSteer` with actor, reason, timestamp and resulting epoch;
- exact retry is idempotent;
- same idempotency key with a changed directive is rejected;
- old contributions remain preserved as evidence but cannot satisfy the new epoch's quorum;
- steering does not issue, widen, revoke or otherwise mutate capability leases;
- capability expansion remains a distinct governed authorization transaction.

## Discriminating tests added

`tests/capt_runtime/test_operator_steering_durable.py` tests the actual command path, not a separate direct call to `epoch.steer()`:

1. operator command causes the EventStore-backed Cohort epoch to advance;
2. old contributions become stale for current quorum;
3. directive and epoch survive close/reopen;
4. exact retry is idempotent;
5. conflicting replay is rejected;
6. authenticated operator identity is enforced;
7. capability aggregate set is unchanged by steering.

## Exact-head verification required

```bash
pytest tests/capt_runtime/test_cohort.py \
       tests/capt_runtime/test_cohort_durability.py \
       tests/capt_runtime/test_operator_steering_durable.py
pytest tests/capt_runtime/test_governed_artifact_promotion.py \
       tests/capt_runtime/test_artifact_workspace.py
pytest
```

Do not promote this item to `IMPLEMENTED_VERIFIED_READY_FOR_OWNER_REVIEW` until exact-head execution evidence exists.
