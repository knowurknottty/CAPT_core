# CAPT-UPG-014 — Epistemic State Ladder

- **Campaign ID:** `CAPT-UPG-014`
- **Issue:** #79
- **PR:** #80
- **Rebuilt base:** corrected CAPT-UPG-013 @ `df5c39c978f822c9d1a5ae2a53961c5391ff1e81`
- **Status:** `IMPLEMENTED_PENDING_EXACT_HEAD_VERIFICATION`

## Delivered

- claim-scoped epistemic projection helper;
- shared Dashboard now preserves `claims` and `verifications_by_claim`;
- multiple claim verification states never collapse into an arbitrary global scalar;
- domain-scoped `VERIFIED:<domain>`, `CONTRADICTED:<domain>`, advisory/committed provenance, stale state, and claim-promotion labels;
- Textual `EpistemicCaptTUI` exposed through `capt-tui`;
- no green-equals-truth semantics and no invented confidence percentage;
- corrected CAPT-UPG-011 `steer_deliberation()` remains present on the shared Operator facade.

## Authority boundary

This is projection only. RuntimeService/EventStore remain authoritative. Evidence, verification, ClaimGuard disposition, claim acceptance and universal truth remain distinct concepts.

## Tests authored

- `tests/test_epistemic_ladder.py`
- `tests/test_operator_epistemic_dashboard.py`

## Verification required

```bash
pytest tests/test_epistemic_ladder.py tests/test_operator_epistemic_dashboard.py
pytest tests/capt_runtime/test_operator_steering_durable.py tests/capt_runtime/test_cohort_durability.py
pytest
```

No exact-head PASS is claimed until observed.
