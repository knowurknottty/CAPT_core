# CAPT-UPG-014 — Epistemic State Ladder

- **Campaign ID:** `CAPT-UPG-014`
- **Issue:** #79
- **PR:** #80
- **Base:** verified CAPT-UPG-013 @ `e41f96f25378beac61b29435e44eef2022d56603`
- **Disposition:** `IMPLEMENTED_VERIFIED_READY_FOR_OWNER_REVIEW`

## Delivered

- claim-scoped epistemic projection helper;
- shared Dashboard preserves `claims` and `verifications_by_claim`;
- multiple claim verification states never collapse into an arbitrary global certainty scalar;
- domain-scoped `VERIFIED:<domain>`, `CONTRADICTED:<domain>`, advisory/committed provenance, stale state, and claim-promotion labels;
- Textual `EpistemicCaptTUI` exposed through `capt-tui`;
- no green-equals-truth semantics and no invented confidence percentage;
- corrected CAPT-UPG-011 `steer_deliberation()` remains on the shared Operator facade.

## Authority boundary

This layer is projection/control only. RuntimeService/EventStore remain authoritative. Evidence recording, domain-specific verification, ClaimGuard disposition, claim acceptance, and universal truth remain distinct concepts.

## Verification

Focused gate on corrected ancestry:

```text
11 passed
EpistemicCaptTUI import: PASS
```

Exact-commit full-suite verification is recorded on PR #80 after this evidence commit. The repository's configured `slow` tests remain excluded from the standard suite.
