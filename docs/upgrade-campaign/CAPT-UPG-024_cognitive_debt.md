# CAPT-UPG-024: Concrete Cognitive Debt Accounting + Operator Surface

- **Campaign ID**: `CAPT-UPG-024`
- **Issue**: #96
- **Branch**: `upgrade/capt-upg-024-cognitive-debt`
- **Disposition**: `IMPLEMENTED_PENDING_EXACT_HEAD_VERIFICATION`

## Implementation

`capt_ui/operator/cognitive_debt.py` emits deterministic, source-linked debt items rather than a single confidence/certainty score.

Current observable debt classes include:

- explicitly required claim missing committed verification;
- contradiction not terminally rejected/suppressed;
- qualified claim;
- explicitly stale verification/evidence;
- pending human approval;
- task recovery/reconciliation required;
- driver recovery/reconciliation required;
- explicitly unknown/indeterminate external effect occurrence;
- capability reservation awaiting reconciliation;
- stale Cohort contribution from a prior epoch;
- current material Cohort dissent/escalation.

Every item binds category + source type + source ID + reason into a deterministic debt ID. Identical source/reason debt is deduplicated.

The projection explicitly sets:

```text
opaqueScalarScore = null
automaticHalt = false
absenceOfDebtProvesCorrectness = false
```

`desktop/cognitive_debt.py` provides a standalone Tk/Aqua cockpit and headless JSON mode. It augments the authoritative desktop projection with capability/cohort aggregate snapshots when those aggregate kinds exist.

`pyproject.toml` adds:

```text
capt-debt = desktop.cognitive_debt:main
```

## Tests authored

`tests/test_cognitive_debt_projection.py` covers concrete debt categories, no invented debt from absent fields, deterministic deduplication, and refusal to emit an opaque score.

## Verification boundary

No exact-head pytest, installed-wheel or rendered-GUI execution is available from the connected environment. No PASS is claimed.

Minimum evidence:

```bash
pytest tests/test_cognitive_debt_projection.py
capt-debt --sock <socket> --token-file <token> --headless
```

plus installed-wheel/desktop smoke verification before owner-ready integration.
