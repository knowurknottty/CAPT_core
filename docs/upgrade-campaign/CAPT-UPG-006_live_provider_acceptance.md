# CAPT-UPG-006: Authenticated Live OpenAI-Compatible Provider Acceptance — Disposition Manifest

- **Campaign ID**: `CAPT-UPG-006`
- **Issue**: https://github.com/knowurknottty/CAPT_core/issues/61
- **Branch**: `upgrade/capt-upg-006-live-provider-acceptance`
- **Base SHA**: `1cf02a3` (`upgrade/capt-upg-005-injection-assurance`)
- **Status**: `BLOCKED_WITH_EXACT_EVIDENCE`

---

## 1. Scope & Execution Report

- **Goal**: Perform live authenticated invocation against an external OpenAI-compatible provider (e.g., OpenRouter / OpenAI) through the governed runtime service path and record real cryptographic non-secret receipts.
- **Environment Audit**:
  - `OPENROUTER_API_KEY`: Not set in current execution environment.
  - `OPENAI_API_KEY`: Not set in current execution environment.
  - Local Ollama daemon (`http://localhost:11434`): Not running / unreachable on host port 11434.
- **Provider Protocol Verification**:
  - `tests/capt_runtime/test_provider_driver.py` proves request format, token scrubbing, authorization header redaction, and `ProviderDriver` transport mechanics across all 4 targeted tests.
- **Disposition**:
  - In accordance with the Owner Audit directive ("*If credentials are unavailable, terminalize as BLOCKED_WITH_EXACT_EVIDENCE, not verified*"), CAPT-UPG-006 is classified as `BLOCKED_WITH_EXACT_EVIDENCE` until live provider credentials or a local daemon are provisioned in the execution environment.

---

## 2. Test Evidence

```bash
pytest tests/capt_runtime/test_provider_driver.py
```

Output:
```
============================== 4 passed in 0.08s ===============================
```
