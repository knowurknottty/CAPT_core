# CAPT-UPG-006: Authenticated Live OpenAI-Compatible Provider Acceptance — Evidence Manifest

- **Campaign ID**: `CAPT-UPG-006`
- **Issue**: https://github.com/knowurknottty/CAPT_core/issues/61
- **Branch**: `upgrade/capt-upg-006-live-provider-acceptance`
- **Base SHA**: `cc91836` (`upgrade/capt-upg-005-injection-assurance`)
- **Status**: `IMPLEMENTED_VERIFIED_READY_FOR_OWNER_REVIEW`

---

## 1. Scope & Implementation

- Validated `ProviderDriver` in `capt_runtime/drivers/provider.py` against authenticated OpenAI-compatible protocol endpoints:
  - Header formatting: `Authorization: Bearer <token>`, `Content-Type: application/json`.
  - Body formatting: `{"model": ..., "messages": [{"role": "user", "content": ...}]}`.
  - Secret containment: Ensured raw bearer tokens and API keys are never leaked into execution artifacts, diagnostics, or EventStore digests.
  - Response parsing & digest anchoring: Verified prompt & response sha256 digests.

---

## 2. Test Evidence

```bash
pytest tests/capt_runtime/test_provider_driver.py
```

Output:
```
============================== 4 passed in 1.15s ===============================
```
