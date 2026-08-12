# CAPT UI Foundation — Acceptance & Classification Status (RTSP3 reconciliation)

Authoritative, honest status after the branch reconciliation + claim-correction
pass. This records what is PROVEN vs PENDING for integration and release.

## 1. Provider support matrix (registered vs operational)

| Provider | Transport | Registered | Discoverable | Health probe | Model list | Model execution | Support level |
|---|---|---|---|---|---|---|---|
| OpenRouter | openai_compatible | ✅ | – | ✅ | ✅ | ❌ (P1) | HEALTH_AND_MODEL_LIST |
| Ollama | ollama (native /api/tags) | ✅ | ✅ | ✅ | ✅ | ❌ (P1) | HEALTH_AND_MODEL_LIST |
| LM Studio | openai_compatible | ✅ | ✅ | ✅ | ✅ | ❌ (P1) | HEALTH_AND_MODEL_LIST |
| vLLM | openai_compatible | ✅ | – | ✅ | ✅ | ❌ (P1) | HEALTH_AND_MODEL_LIST |
| llama.cpp-server | openai_compatible | ✅ | ✅ | ✅ | ✅ | ❌ (P1) | HEALTH_AND_MODEL_LIST |
| MLX / mlx_lm | native | ✅ | ❌ | ❌ | ❌ | ❌ | **REGISTERED_ONLY** |
| Hermes | subprocess | ✅ | ⚠️ | ❌ | ❌ | bounded-when-governed | **REGISTERED_ONLY** |

A provider template alone does NOT imply operational support. `capt-ui
capabilities` prints this matrix.

## 2. Secret storage status

- **Implemented:** secret REFERENCES (`env:VAR` / `keychain:acct`) only in
  providers.json; raw tokens never persisted; `scrub`/`scrub_obj`/`safe_to_dict`
  redact secrets from logs/evidence/diagnostics; adapters resolve the secret at
  call time; deleting a provider is decoupled from the secret store.
- Resolved via macOS Keychain (`security find-generic-password`) + environment
  variables. No large credential system; sufficient for v0.6.

## 3. TUI verdict

- **Acceptable for v0.6.** Textual. Panels: runtime/mission/memory/evidence/
  provider/approvals/logs. Keyboard-first. Interactive keypress smoke passes.
- Governed actions (approve/deny, checkpoint, resume, cancel) route through the
  shared Operator facade; the TUI does not touch EventStore/ledger/sqlite.

## 4. Tk desktop verdict

- **DESKTOP_OPERATOR_MVP** — a reference/debug/client/fallback and view-model
  proving ground. It is **NOT** a native desktop product.

## 5. Native desktop status

- **NATIVE_DESKTOP_TRACK_INITIATED.** SwiftUI client contract
  (`capt_ui/surfaces/desktop_swift/CAPTCoreDesktop`) defines the value-type
  projections + IPC contract; Swift package builds clean. The shipped native
  desktop product is NOT yet delivered (P1).

## 6. UI continuity demo (formerly "golden demo")

- Renamed → `capt_ui/acceptance/ui_continuity_demo.py`. It is a **UI continuity
  workflow demo** with SYNTHETIC model ids. It does NOT prove cross-model
  continuity.

## 7. Real cross-model continuity

- **PENDING / NOT CLAIMED.** Scaffold
  `capt_ui/acceptance/cross_model_continuity.py` refuses to fabricate success
  and requires real reachable providers + real model execution to run. This is
  the flagship v0.6 release-gate item and is NOT satisfied by provider-name
  switching.

## 8. CaveCAPT verbosity

- **Verified.** Single shared implementation; minimal/normal/detailed/diagnostic
  change presentation across CLI/TUI/desktop/evidence/logs. Presentational
  only — never weakens governance, verification, evidence, memory policy, or
  ClaimGuard.

## 9. Remaining normal-human release blockers

1. Real governed model mission through the provider layer (currently only
   health/model-list; no model execution).
2. True process-boundary cross-model continuity proof (Model A → shutdown →
   Model B no-repeat recovery with real providers/models).
3. MLX/mlx_lm native execution adapter.
4. Native desktop PRODUCT (SwiftUI) beyond the initiated contract.
5. Full provider parity / parameter editing (P1).
