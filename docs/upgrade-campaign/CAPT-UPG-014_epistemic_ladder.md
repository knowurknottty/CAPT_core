# CAPT-UPG-014: Epistemic State Ladder

- **Campaign ID**: `CAPT-UPG-014`
- **Issue**: #79
- **Branch**: `upgrade/capt-upg-014-epistemic-ladder`
- **Disposition**: `IMPLEMENTED_PENDING_EXACT_HEAD_VERIFICATION`

## Source changes

- `capt_ui/operator/epistemics.py`
  - pure, non-authoritative claim-scoped epistemic projection;
  - separates evidence, verification domain/status, committed/advisory provenance, and ClaimGuard/claim promotion state;
  - never emits an absolute truth/certainty state.
- `capt_ui/operator/contract.py`
  - Dashboard now carries `claims`, `verifications_by_claim`, and `epistemic_ladder`.
- `capt_ui/operator/runtime.py`
  - repairs the pre-existing projection mismatch where `project_authoritative_state()` returned `verificationsByClaim` but Dashboard read a nonexistent `verification` key;
  - preserves a backward-compatible scalar only when exactly one claim exists;
  - explicitly emits `claim_scoped` instead of selecting an arbitrary verification when multiple claims coexist.
- `capt_ui/surfaces/tui/epistemic_app.py`
  - additive `CaptTUI` subclass that renders the shared Dashboard ladder in the existing EvidencePanel;
  - clarifies that `VERIFIED:<domain>` is domain-scoped and Claim acceptance is separate.
- `pyproject.toml`
  - adds `capt-tui = capt_ui.surfaces.tui.epistemic_app:main`.

## Tests authored

- `tests/test_epistemic_ladder.py`
  - verified vs accepted separation;
  - contradicted/rejected state;
  - advisory observed-unverified state;
  - stale state only when source data marks it;
  - multiple claims remain separate.
- `tests/test_operator_epistemic_dashboard.py`
  - locks the `verificationsByClaim` Dashboard projection and multi-claim behavior.

## Verification boundary

No exact-head test execution is available in the connected environment. No PASS is claimed.

Required minimum execution:

```bash
pytest tests/test_epistemic_ladder.py tests/test_operator_epistemic_dashboard.py tests/test_ui_tui.py tests/test_tui_dogfood.py
```

and installed-wheel `capt-tui` launch/import proof before owner-ready status.
