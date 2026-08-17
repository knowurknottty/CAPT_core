# CAPT-UPG-001: Wire Bounded Production IPC Framing — Evidence Manifest

- **Campaign ID**: `CAPT-UPG-001`
- **Issue**: https://github.com/knowurknottty/CAPT_core/issues/51
- **Branch**: `upgrade/capt-upg-001-ipc-framing`
- **Base SHA**: `989c45b22e4b336fd66886d59434490cf28e119a` (`feat/security-infrastructure-gate` PR #49)
- **Status**: `IMPLEMENTED_VERIFIED_READY_FOR_OWNER_REVIEW`

---

## 1. Scope & Implementation

Replaced unbounded line-based and raw socket buffer parsing in `desktop/capt_runtime_service.py` and `desktop/desktop_runtime_client.py` with bounded framed transport using `capt_runtime.ipc_framing`:
- `recv_json` / `send_json` with `MAX_FRAME_BYTES = 4 * 1024 * 1024`.
- Strict rejection on truncated headers, oversized lengths, non-dict payloads, and invalid JSON encoding.
- Fail-closed disconnection without daemon crash when receiving adversarial or malformed frames.

---

## 2. Test Evidence

```bash
pytest tests/capt_runtime/test_bounded_ipc_framing.py \
       tests/capt_runtime/test_desktop_m0.py \
       tests/capt_runtime/test_desktop_m1.py \
       tests/capt_runtime/test_desktop_m1_security.py \
       tests/capt_runtime/test_desktop_m1_adversarial.py
```

Output:
```
============================== 47 passed in 3.72s ==============================
```

---

## 3. Residual Limitations

- The Python desktop runtime IPC is now fully bounded. Swift native transport bindings will consume this protocol once Swift IPC client is exercised.
