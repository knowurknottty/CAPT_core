# CAPT-UPG-003: Durable Security Rejection Audit Trail — Evidence Manifest

- **Campaign ID**: `CAPT-UPG-003`
- **Issue**: https://github.com/knowurknottty/CAPT_core/issues/55
- **Branch**: `upgrade/capt-upg-003-security-audit-trail`
- **Base SHA**: `6689353` (`upgrade/capt-upg-002-state-permissions`)
- **Status**: `IMPLEMENTED_VERIFIED_READY_FOR_OWNER_REVIEW`

---

## 1. Scope & Implementation

- Added `security_rejections` table and persistence methods `record_security_rejection` / `list_security_rejections` to `capt_runtime/store.py`.
- Wired failed authentication attempts in `desktop/capt_runtime_service.py` into durable security rejection records without leaking secrets.

---

## 2. Test Evidence

```bash
pytest tests/capt_runtime/test_security_audit_trail.py
```

Output:
```
============================== 1 passed in 0.10s ===============================
```
