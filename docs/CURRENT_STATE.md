# CAPT Core — Current State

This is the concise public status source for the repository.

## Four truth classes

### 1. Numbered package release

`pyproject.toml` still declares **`capt-solo 0.5.0`**. Preserved installed-wheel and release evidence under `release_evidence/v0.5/` applies to that release lineage.

### 2. Merged `main`

`main` is materially newer than the original v0.5 package release. It includes the v0.6 productization foundation:

- normal `capt start/status/stop/checkpoint/resume/evidence/doctor` on-ramp;
- durable memory commands;
- shared `capt_ui.operator` layer;
- provider registration, health/model discovery where supported, and model-selection foundations;
- CaveCAPT presentation verbosity;
- Textual TUI MVP with governed approve/deny and operator panels;
- Tk desktop operator MVP;
- SwiftUI client-contract library;
- onboarding and UI continuity scaffolding.

These merged surfaces do **not** by themselves prove a real cross-model release acceptance.

### 3. Active cumulative integration stack

| PR | Area | Status boundary |
|---|---|---|
| #44 | Discovery Governor + bounded scanner | implemented/local integration evidence; unmerged |
| #46 | Ouroboros/Hermes lifecycle | hardened lifecycle/recovery; unmerged |
| #47 | prompt/cognitive provenance + TUI cockpit + ProviderDriver | exact-head source/editable full-suite verified; unmerged; installed/live-provider proof still open |
| #48 | Cohort coordination | bounded coordination contracts; durable runtime integration still later |
| #49 | security gate | draft and intentionally blocked pending closure evidence |

PR #47 adds the most visible operator delta: `MAX/SPOCK/CAVE CAPT/MIN` response modes, 32K–256K requested context budgets, `OFF/AUTO/OMNI/META/FORGE/SIGMA` prompt-enhancement selection, explicit human review/approval, prompt-assembly provenance, and a bounded provider execution driver.

The active ProviderDriver has real Ollama and OpenAI-compatible HTTP transport code and controlled HTTP protocol tests. At PR #47 head `4334657a919f74803e65d9b01aa5054d6d7b9a61`, clean verification passed 8 approval-security tests, 31 focused prompt/provider/TUI/operator tests, 18 Ouroboros lifecycle tests, 387 `capt_runtime` tests, and 861 full-repository tests. That is **exact-head source/editable proof**, not live-provider or installed-runtime acceptance.

### 4. Release proof

A capability becomes release-proven only when the exact relevant source, execution path, evidence, and release artifact agree. Historical v0.5 evidence stays historical; PR-local focused tests stay PR-local.

## Hermes LOCAL-002 metadata — currently unverifiable

The operator previously supplied:

- branch `evidence/hermes-local-002-r6`;
- HEAD `5c8cbf5ec1dfc0034ba7fa0931e21c88fe0cfc04`;
- report `reports/local-evidence/HERMES_AGENT_TUI_WORKSPACE_TESTS_AND_STATE_MAP_8F97AE9_2026-08-17.md`;
- classification `HERMES_LOCAL_002_COMPLETE`;
- Node `v22.22.2`, system npm `11.14.1` engine-incompatible, workspace npm `11.17.0` via `npx`;
- focused 98 passed / 0 failed / 0 skipped;
- broader 174 passed / 0 failed / 2 skipped;
- no product/state-map blocker.

Terra independently checked the current remote/API and found the supplied branch, commit, and named report absent. The metadata above is therefore **operator-supplied and currently unverified**. The earlier connector-lag explanation is withdrawn; current repository state does not support treating LOCAL-002 as published evidence.

This quarantine does not alter preserved historical v0.5 Hermes proof. If LOCAL-002 is restored, the report must be independently retrieved and reconciled before its claims are promoted. Even then it would remain adjacent workspace evidence, not proof of PR #47 exact-head correctness, an installed wheel, a live provider, destructive rollback, process-boundary restart continuity, or release readiness.

## Current highest-value unresolved gates

- merge/reconcile the cumulative integration stack without losing authority invariants;
- exact-terminal-head integrated suite and installed-runtime proof;
- live provider acceptance for the intended provider path(s);
- true process-boundary cross-model continuity proof;
- durable Cohort persistence/reconstruction/evidence admission before durable Cohort claims;
- security PR #49 closure, including known at-rest, IPC framing, rejection-audit, file-permission, resource-ceiling, and adversarial prompt/context assurance gaps;
- native desktop product remains beyond the shipped Tk MVP / SwiftUI library contract.

## Authority invariant

```text
Operator surfaces
  CLI / TUI / Desktop / compatibility clients
                |
                v
        authenticated RuntimeService
                |
       governance + EventStore
       memory/context + evidence
       DriverHost / bounded drivers
                |
                v
        replaceable inference models
```

No UI, model, compatibility client, Cohort projection, security checker, or prompt-enhancement engine becomes a parallel source of authoritative CAPT state.