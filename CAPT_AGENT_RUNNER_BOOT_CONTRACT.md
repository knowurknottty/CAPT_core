# CAPT_AGENT_RUNNER_BOOT_CONTRACT.md

Canonical boot contract for the standalone CAPT Agent Runner. Fail-closed.

## Execution modes

- GOVERNED — all mandatory checks pass.
- BOOTSTRAP_DEGRADED — explicit owner authorization only; records missing
  controls, reason, allowed ops, prohibited ops, expiry/scope, evidence.
- BLOCKED (default on any mandatory failure) — no model invocation.

Default to BLOCKED when mandatory memory, mission, checkpoint integrity,
ContextPack validation, or MemoryUseGate fails. Never silently continue
ungoverned. No transcript fallback may satisfy boot.

## Boot pipeline (before first provider invocation)

1. Validate runtime configuration (`RuntimeConfiguration.from_env`).
2. Resolve workspace identity (path + git SHA/branch).
3. Resolve mission (from store; NOT hard-coded).
4. Resolve or create session (`SessionRuntime.begin`).
5. Load latest valid checkpoint (integrity-checked; stale → BLOCKED).
6. Retrieve active owner directives.
7. Retrieve mandatory protected memory.
8. Retrieve task-relevant semantic/episodic/procedural/decision/provenance/
   receipt/unresolved-work memory.
9. Identify stale, superseded, revoked, conflicting, rejected, missing records.
10. Build bounded ContextPack (`build_context_pack`).
11. Validate ContextPack (`validate_context_pack`).
12. Pass MemoryUseGate (`MemoryUseGate.prepare` → `GateDecision.allowed`);
    non-PASS → BLOCKED (durable: CTP abort + failed event).
13. Persist boot artifact + digest (AgentMemoryBootTrace).
14. Begin CTP model-turn transaction.
15. Publish KHSB start events.
16. Invoke model through canonical ModelProvider.

No model invocation before step 12 PASS. Steps 1-12 gate step 16 at RUNTIME
(not prompt). Composes `CAPTRuntime.execute_model_task` (runtime.py:577) which
already enforces the gate-before-invoke order (runtime.py:636-674).

## Data contracts (typed; reuse repo types, do not duplicate)

```python
@dataclass(frozen=True)
class AgentMemoryBootTrace:
    agent_run_id: str
    mission_id: str
    session_id: str
    checkpoint_id: str
    active_directive_ids: tuple[str, ...]
    selected_memory_ids: tuple[str, ...]
    rejected_memory_ids: tuple[str, ...]
    stale_memory_ids: tuple[str, ...]
    conflict_ids: tuple[str, ...]
    missing_memory_ids: tuple[str, ...]
    contextpack_digest: str
    memory_use_decision_id: str
    gate_result: str            # PASS | BLOCKED | DEGRADED
    model_request_artifact_id: str
    created_at: str
```

Also: AgentBootRequest, AgentBootResult, AgentRunState, AgentTurnRequest,
AgentTurnResult, ContextBudgetState, AgentCheckpoint, AgentRecoveryResult,
OutputPolicy. Reuse `Mission/MissionIntent/Assumption/RecordRef/ProtectedFact/
TokenBudget` (contextpack/core.py), `Checkpoint/RestartPacket`
(lifecycle/sessions.py), `ModelTaskRequest/Result/Identity` (model_task.py).
Keep schemas versioned; provide migration readers for legacy records.

## KHSB events (typed durable)

agent.boot.requested, agent.boot.memory_retrieved, agent.boot.context_validated,
agent.boot.completed, agent.boot.failed, agent.turn.started,
memory.retrieval.started, memory.retrieval.completed, contextpack.created,
memory.gate.passed, memory.gate.failed, model.task.started,
model.task.completed, model.task.failed, claim.submitted, claim.supported,
claim.unsupported, ctp.started, ctp.committed, ctp.aborted, agent.checkpointed,
agent.context.consolidated, agent.session.completed, agent.session.failed,
agent.resumed. Each carries mission, session, run, turn, correlation,
transaction, provider/model, git SHA, artifact IDs. Idempotent consumers
(`_DurableEventLog`, runtime.py:333).

## Turn loop

resolve state → retrieve memory → resolve directives/contradictions → assemble
bounded ContextPack + only necessary recent interaction → MemoryUseGate →
idempotent CTP begin → persist request artifact → ModelProvider.invoke →
persist normalized response → extract claims → ClaimGuard → persist decisions/
unresolved/evidence → commit|abort CTP → publish events → checkpoint → enforce
context budget → continue | checkpoint-and-exit | block. Full historical
transcript is NOT fed by default.

## Model request layers (distinct + hashed)

Constitution; runtime protocol; model profile; memory profile; mission; active
directives; selected ContextPack; unresolved state; bounded recent interaction;
current task. Use CAPT Space material where available; transitional layer
assembler allowed (clearly marked) — V1 not blocked on the full Space compiler.
First post-boot user input is CURRENT-TASK input, not continuity state.
