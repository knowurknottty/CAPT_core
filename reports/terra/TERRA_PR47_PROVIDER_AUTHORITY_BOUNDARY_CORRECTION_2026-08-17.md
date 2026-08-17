# TERRA PR #47 provider-authority boundary correction

Classification: `PROVIDER_AUTHORITY_BOUNDARY_VERIFIED_WITH_CORRECTIONS`

## Identity

- Remote starting PR head: `4ee85af818008c2536faaaefa0e7ec00ac2a39c4`
- Intermediate commits: `75331ce0c7ca7fb8eb6d4884a7b4d426af06e72a`, `cc89b064241b7727dc00bda72227e31335075ad1`
- Verified candidate: `10854b5a2b9835788478ee7770fcaa17bb4e1156`
- Wheel: `capt_solo-0.5.0-py3-none-any.whl`, SHA-256 `db3ee232320e4a1cd63556c03813285dab24429e9c590e2712a7242145fc05e1`
- Sdist SHA-256: `ba0ec1ffbc9a44f630d9ad5fbce8b7b30e6515d240716930e4c9eec2bb62dbec`

## Correction

`PreparedApprovedModelExecution` is immutable and has a deterministic non-secret prepared-execution digest. Deterministic preparation occurs before admission. `RuntimeService.admit_approved_model_execution` atomically records approval consumption, durable driver-run intent, and command idempotency via `EventStore.commit_command`. The executor receives the prepared execution, not raw command inputs. Provider success records evidence and transitions the task to `awaiting_verification`; it does not automatically record verification, accept a claim, or complete task/mission.

## Source and installed evidence

- Focused candidate suites: `37 passed`.
- Full candidate suite: `875 passed, 57 skipped, 12 deselected`.
- Fresh installed copied prepared-execution suite: `12 passed`.
- Isolated installed imports resolved from `site-packages` for CAPT runtime, prepared execution, runtime service, command service, UI, and generated contracts.

## Real installed Ollama acceptance

Provider: local Ollama native `/api/generate`.
Model: `qwen3.5-defiant-fable:latest`.

A real installed-runtime run completed, followed by exact replay, different-second-use rejection, fresh approval/new execution, and clean runtime restart. Both completed tasks reconstructed as `awaiting_verification`; event count remained `44 -> 44` across restart. The authoritative event store contained zero `VerificationRecorded`, zero `ClaimGuardDecided`, and zero task-success events. Ordered post-admission execution events were:

`DriverRunCreated -> DriverRunStateChanged(submitted) -> DriverRunStateChanged(running) -> CapabilityUseReserved -> DriverRunStateChanged(completed) -> CapabilityUseFinalized -> ClaimCreated -> EvidenceRecorded -> TaskTransitioned(awaiting_verification)`.

Exact replay produced no event delta and no second provider inference. Different second use was rejected with `MODEL_PROMPT_APPROVAL_DIGEST_MISMATCH` and produced no event delta.

## Live deterministic no-consume proof

A separate fresh installed runtime approved each invalid payload before execution:

- `requestedContextBudget=12345` then rejected as `REQUESTED_CONTEXT_BUDGET_INVALID`;
- approved objective length `513` then rejected as `MODEL_VISIBLE_PROMPT_TITLE_TOO_LONG`.

For each: `remainingUses=1`, run event delta `0`, no `HumanApprovalConsumed`, no driver-run events, and no dispatch-trap request.

## Crash/restart and limits

The candidate source coverage includes the controlled post-admission/replay safety seams. Installed clean restart from `awaiting_verification` caused no redispatch. This gate did not kill Ollama during inference. Authenticated OpenAI-compatible transport remains unverified. Hermes LOCAL-002/D-09 remains quarantined and was not used.

## Evidence inputs

- Real acceptance projection SHA-256: `5fd98afab9b7d4092e6931606c2220b2f276c8612b9297a4c1a331c7ad405268`
- Live no-consume projection SHA-256: `f96e5b7340c91c263ac59167fc40aac70323041bc0611f4cf6bb05cddda70fe5`
