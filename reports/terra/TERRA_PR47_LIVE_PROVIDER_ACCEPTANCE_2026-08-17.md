# TERRA PR #47 live intended-provider acceptance — 2026-08-17

## Classification

`NOT_VERIFIED`

A real local Ollama native-provider inference was executed through the installed, approval-bound CAPT runtime. The gate is not verified because authoritative reconciliation collapses a provider response into verification, ClaimGuard acceptance, and task success. That contradicts the required evidence boundary for this gate. No authenticated OpenAI-compatible live execution was attempted or claimed.

## Authority / artifact / provenance

- PR #47 head freshly verified: `4ee85af818008c2536faaaefa0e7ec00ac2a39c4`.
- Installed-wheel evidence commit freshly verified: `29c9ebed583755e266e3d9c36bcc5b03d36f38ce`.
- Reused exact wheel: `capt_solo-0.5.0-py3-none-any.whl`, SHA-256 `152febe1dab1148d007e84f4461c369533ba4628d8f6306836ffcd84dd0ec1d5`.
- New non-editable venv; sandbox CWD; empty `PYTHONPATH`; `PYTHONNOUSERSITE=1`; `python -I`.
- Runtime/client imports resolved from fresh venv site-packages.

## Provider preflight

- Provider: Ollama, local, native `/api/generate`, authentication not applicable.
- Endpoint probe: local `/api/tags` returned HTTP 200 and listed `qwen3.5-defiant-fable:latest`.
- Selected real model: `qwen3.5-defiant-fable:latest`.
- OpenRouter credential-name presence was observed without reading or recording its value; authenticated OpenAI-compatible transport was not exercised.

## Actual governed live run

The installed runtime executed this real path:

`RuntimeClient -> request_model_prompt_approval -> HumanApprovalRequested -> HumanApprovalDecided -> run_approved_hermes_inspection -> approval admission -> ProviderDriver(ollama) -> real Ollama /api/generate -> response_completed -> reconciliation`.

- Challenge nonce: `CAPT-LIVE-ac133b8a41df413d`.
- Human objective: `Return CAPT-LIVE-ac133b8a41df413d; 17+25.`
- Mission/task/driver/request: `m-live-ollama-3` / `t-live-ollama-3` / `dr-live-ollama-3` / `approval-live-ollama-3`.
- Prompt assembly digest: `sha256:11d76fa9b2cbfda7b5277ffce6deae91c58f0c99b4201c617cb849d388b3683e`.
- Final dispatch digest: `sha256:7f7fa3ba6cc80a05ec2b48d22f64549c335058267d14f045be74635085bfa55b`.
- Provider response digest: `sha256:f6c73155e4495ff4bfc5448bea25838ce3d93981bbbf867229a548b4dcd826db`.
- Dispatch state: `response_completed`; elapsed 25.672 seconds.
- Returned response contained the nonce and `17 + 25 = 42`.
- Requested context budget: 32000; recorded effective context budget: 8192.
- `HumanApprovalConsumed` state was durable: `remainingUses=0`.

## Failure findings

1. **Boundary violation: provider response is automatically promoted.** The real provider response resulted in an evidence record, verification result, accepted ClaimGuard decision, and task state `succeeded` in the same runtime command. The observed source path performs `record_evidence`, `record_verification`, `decide_claim`, and `transition_task(..., "succeeded", ...)` after provider response. The live EventStore confirmed task `t-live-ollama-3` state `succeeded`. Therefore provider output is not retained as merely untrusted provider output pending separate evidence/verification/claim authority.

2. **Pre-dispatch validation consumes approval.** A longer challenge produced `TaskNode: title: longer than maxLength 512` before provider dispatch. Its approval nevertheless became consumed (`remainingUses=0`). This is a live failure-path finding; no external request occurred for that attempt. The successful live run used a shorter challenge whose generated model-visible prompt was within the current title bound.

No production correction was applied: these authority/lifecycle defects require contract and runtime design review; a narrow patch would risk changing the frozen task/execution contract without resolving the authority conflation.

## Secret check

The local Ollama path used no credential. EventStore aggregate inspection reported no `Authorization` header and no `OPENROUTER_API_KEY` reference. No raw credential value was read, printed, persisted, or committed.

## Five-pass recursion ledger

1. Source reconstruction: independently re-fetched PR/evidence refs, read prior wheel artifacts, traced planner, RuntimeService, RuntimeCommandService, task resolver, ProviderDriver, and reconciliation.
2. Authority review: distinguished RuntimeService/EventStore authority from client/UI receipts and traced approval consumption plus post-response state transitions.
3. Failure-path review: exercised invalid context budget and title-length failures without provider dispatch; inspected durable consumed state.
4. Evidence calibration: fresh installed wheel environment, live endpoint preflight, nonce challenge, provider/model/digest/response timing, and secret-free reporting.
5. Contradiction removal: compared source transition sequence with EventStore state; classified the gate NOT_VERIFIED rather than treating a real HTTP/model response as evidence/verification/claim proof.

## Remaining gates

- Correct the provider-output authority/consequential-state boundary and rerun this entire gate on a new exact head.
- Authenticated OpenAI-compatible live transport remains unexecuted.
- Cross-model process-boundary continuity, destructive provider/tool-kill rollback, #49 security, Cohort durability, native desktop, deployment, and release gates remain open.

D-09 Hermes LOCAL-002 remains quarantined and was not used.
