# CAPT_AGENT_RUNNER_IMPLEMENTATION_PLAN.md

Minimum viable standalone CAPT Agent Runner. Compose existing canonical systems;
do not clone Hermes; do not duplicate runtime subsystems.

## New composition surface (only new code)

`capt_solo/agent/`
- `contracts.py` — AgentBootRequest, AgentBootResult, AgentRunState,
  AgentTurnRequest, AgentTurnResult, AgentMemoryBootTrace, ContextBudgetState,
  AgentCheckpoint, AgentRecoveryResult, OutputPolicy. Frozen dataclasses;
  versioned; migration readers for legacy. Reuse repo types (Mission/
  MissionIntent/Assumption/RecordRef/TokenBudget, Checkpoint/RestartPacket,
  ModelTaskRequest/Result/Identity) — no duplicates.
- `directives.py` — active-directive resolution + explicit supersession
  (STATE_AUTHORITY).
- `render.py` — distinct+hashed layer assembler (Constitution/protocol/model
  profile/memory profile/mission/directives/ContextPack/unresolved/recent/task);
  transitional if Space compiler absent.
- `context_budget.py` — %-threshold policy + transactional consolidation
  (CONTEXT_POLICY).
- `output.py` — runtime-owned OutputPolicy renderer (cave default; normal/
  verbose/silent/audit); safety messages bypass caps.
- `boot.py` — 16-step boot pipeline (BOOT_CONTRACT); modes GOVERNED/
  BOOTSTRAP_DEGRADED/BLOCKED; fail-closed.
- `runner.py` — turn loop over `CAPTRuntime.execute_model_task`; owns CTP/KHSB/
  ClaimGuard/checkpoint/exit/resume via CAPTRuntime.

CLI: add `agent` group in `capt_cli.py` (start/resume/status/checkpoint/doctor;
`--output-mode`, `--mission`, `--workspace`), dispatch via `args.group ==`
(capt_cli.py:326-350). Additive; no existing group changed.

## Reuse map (import via capt_solo/api.py only)

CAPTRuntime/execute_model_task (runtime.py:577); MemoryUseGate (runtime.py:209);
GateDecision/GateDeniedError; build/validate_context_pack + ContextPack types
(contextpack/core.py); ModelProvider + OpenAICompatibleLocalProvider
(model_task.py); SessionRuntime/Checkpoint/RestartPacket (lifecycle/sessions.py);
CTPRuntime/Receipt; KHSB/Message + _DurableEventLog (runtime.py:333); ClaimGuard/
ProofEngine/CapabilityRegistry (foundry); MemoryEngine.

## Implementation order (fresh process)

1. Recover checkpoint through CAPT. 2. Verify mission/directives/selected memory/
next action. 3. contracts.py. 4. runner composition. 5. boot path. 6. one-turn
no-tool execution. 7. checkpoint + fresh resume. 8. bounded multi-turn loop.
9. context-budget/consolidation. 10. CaveCAPT renderer. 11. CLI. 12. evidence/
reconstruction path. 13. acceptance tests. 14. focused suites. 15. full suite.
16. commit + push.

After each behavioral patch: syntax check; focused tests; inspect diff; no
placeholder; no fake provider; no duplicated CAPT component; no hardcoded
verdict; no unconditional success output.

## Tests

boot contract; mission ambiguity; checkpoint integrity; directive supersession;
ContextPack/gate; no-provider-call-on-denial; model-request layer; event
ordering; CTP commit/abort; ClaimGuard linkage; context budget; fresh-process
integration; transcript contradiction; memory ablation; package/CLI; no-
duplicate-composition-root; CaveCAPT (suppresses tool/planning narration,
preserves blockers/failures, ClaimGuard-safe completion, silent emits nothing on
success, audit includes verdict+evidence, caps never truncate safety, provider
cannot bypass renderer, resumed session retains mode, owner override next turn,
verbose available). Run focused + distribution-contract + canonical full suite;
report exact commands + results.

## Acceptance gates (execution deferred to fresh process)

AC1 fresh boot; AC2 memory-failure block (provider invoke_count==0, CTP abort,
failed events, no success verdict); AC3 transcript contradiction (CAPT wins,
conflict recorded); AC4 two-process continuity (no copied summary/transcript);
AC5 memory materiality/ablation; AC6 context pressure (consolidate before
overflow, fresh resume, no native compaction).

First acceptance immediate input (no answer in prompt): "Resume the active
mission and report the next justified action." Output mode cave; expected compact
output e.g. "Mission resumed. / Current milestone: CAPT Agent Runner
implementation. / Next action: add canonical boot path."

## Milestone gating

Claim GOVERNED_AGENT_BOOT_PROVEN + GOVERNED_AGENT_CONTINUITY_PROVEN only after
AC1+AC4 pass with persisted evidence. Do NOT claim GOVERNED_TOOL_LOOP_PROVEN
(no tools in V1). Do not advance to tools until fresh boot, continuity, memory
materiality, and context handoff pass.

## Guardrails

One composition root (CAPTRuntime); runner composes, never re-implements. No
storage/API break. Provider never decides verbosity. Transcript never re-enters
as authority (STATE_AUTHORITY tier 8).
