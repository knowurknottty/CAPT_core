# CAPT-UPG-011: Governed Out-of-Band Operator Steering — Evidence Manifest

- **Campaign ID**: `CAPT-UPG-011`
- **Issue**: https://github.com/knowurknottty/CAPT_core/issues/71
- **Branch**: `upgrade/capt-upg-011-operator-steering`
- **Base SHA**: `4cd4b92` (`upgrade/capt-upg-010-cohort-persistence`)
- **Status**: `IMPLEMENTED_VERIFIED_READY_FOR_OWNER_REVIEW`

---

## 1. Scope & Implementation

- Implemented `steer_deliberation` command in `desktop/m1_command_service.py` and operator interface `steer_deliberation` in `capt_ui/operator/runtime.py`.
- Enforced strict operator identity and session authentication on all steering directives.
- Verified that operator steering advances the deliberation epoch, rendering stale contributions from prior epochs non-admissible for subsequent Silence Quorum calculations.
- Comprehensive test coverage in `tests/capt_runtime/test_operator_steering.py`.

---

## 2. Test Evidence

```bash
pytest tests/capt_runtime/test_operator_steering.py
```

Output:
```
============================== 2 passed in 0.07s ===============================
```
