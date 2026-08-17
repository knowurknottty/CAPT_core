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
| #47 | prompt/cognitive provenance + TUI cockpit + ProviderDriver | near-complete integration slice; unmerged |
| #48 | Cohort coordination | bounded coordination contracts; durable runtime integration still later |
| #49 | security gate | draft and intentionally blocked pending closure evidence |

PR #47 adds the most visible operator delta: `MAX/SPOCK/CAVE CAPT/MIN` response modes, 32K–256K requested context budgets, `OFF/AUTO/OMNI/META/FORGE/SIGMA` prompt-enhancement selection, explicit human review/approval, prompt-assembly provenance, and a bounded provider execution driver.

The active ProviderDriver has real Ollama and OpenAI-compatible HTTP transport code and controlled HTTP protocol tests. That is **not yet equivalent to exact-head live-provider installed-runtime acceptance**.

### 4. Release proof

A capability becomes release-proven only when the exact relevant source, execution path, evidence, and release artifact agree. Historical v0.5 evidence stays historical; PR-local focused tests stay PR-local.

## Hermes local workspace evidence — `HERMES_LOCAL_002_COMPLETE`

The operator has published the dedicated evidence branch `evidence/hermes-local-002-r6` at HEAD `5c8cbf5ec1dfc0034ba7fa0931e21c88fe0cfc04` with report:

`reports/local-evidence/HERMES_AGENT_TUI_WORKSPACE_TESTS_AND_STATE_MAP_8F97AE9_2026-08-17.md`

Reported test/runtime evidence:

- Node `v22.22.2`;
- system npm `11.14.1` is engine-incompatible for the faithful workspace path;
- faithful workspace npm `11.17.0` was used via `npx`;
- focused suite: **98 passed / 0 failed / 0 skipped**;
- broader suite: **174 passed / 0 failed / 2 skipped**;
- classification: **`HERMES_LOCAL_002_COMPLETE`**;
- no product blocker and no state-map blocker.

Remaining bounded gaps in that evidence record:

- no destructive end-to-end external-provider/tool-kill rollback test;
- two pytest skips remain;
- an unrelated macOS case-insensitive contributor-email checkout collision remains outside the product/state-map result.

The operator also supplied related identities `46e7162dfa2bfb28ced981881e5dded0e74f078e` and `8f97ae9aec729bcbbad17da462115e1ec1398421`; this document does not infer roles for those hashes beyond the evidence report until the repository record itself provides their labels.

At documentation-write time, the GitHub connector had not yet propagated the just-pushed branch even though the operator's `git ls-remote` showed the exact remote ref. Therefore this section records the exact pushed evidence metadata without fabricating connector retrieval. Once GitHub indexing catches up, the report itself is the authority.

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