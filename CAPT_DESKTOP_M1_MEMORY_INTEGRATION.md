# CAPT Desktop M1 Memory Integration (M1-memory, ADR-DT-M1-MEM-001)

## Operator workflow (mission §15)

The Desktop M1 governed operator workflow now includes memory:

1. operator creates mission → `RuntimeCommandService.create_mission` fires the
   mandatory retrieval trigger (`require_retrieval_before_planning`) before
   planning.
2. memory query fires → `build_memory_query` → `MemoryStore.query`.
3. selected/excluded memory appears → ContextPack `selectedRecords` /
   `excludedRecords` (visible in the runtime state projection).
4. ContextPack digest appears → `contextPackDigest` recorded in the pack and
   linked to dispatch.
5. approval view includes relevant historical memory → the seeded store carries
   prior-approval / operator-preference / failed-approach records; the retrieval
   trigger surfaces them.
6. denial prevents execution → approval denial blocks the DriverWorkOrder.
7. approved mission dispatches only the ContextPack slice → `DriverHost.dispatch`
   attaches `contextPackRef`; Hermes receives only the slice reference.
8. cancellation consults lifecycle memory → `cancel_task` / `cancel_driver_run`
   are governed commands; the engine retains trigger state.
9. post-run memory-promotion candidates appear → `evaluate_promotion` returns
   candidates (verified=False, requiresEvidence=True).
10. operator or policy accepts/rejects promotion → `accept_promotion` persists a
    record (trust=unverified, verification_status=pending).
11. reconnect reconstructs trigger policy and memory references →
    `reconstruct_policy` + `last_context_pack`.
12. replay does not repeat retrieval/promotion/execution improperly → idempotent
    trigger state + policy log.

## Operator controls (Tab 5: "Memory Trigger")

`desktop/desktop_app.py` `DesktopApp` exposes:
- `get_memory_policy()` — read-only projection of active policy.
- `get_memory_state(mission_id)` — read-only projection of memory path state.
- `gui_update_memory_trigger_policy(...)` — submits the `update_memory_trigger_policy`
  governed command. The GUI Tab 5 has step inputs for retrieval / compression /
  checkpoint / consolidation / hard-stop, a Refresh button, and an Apply button
  that submits the command and displays ACCEPTED / DENIED.

The UI validates steps are integers in [1, 8] before submission; the runtime
re-validates and persists. The desktop never mutates config or runtime state
directly.

## Evidence

- `tests/capt_runtime/test_memory_trigger_desktop.py` (5 tests) exercises the
  real server + `DesktopApp` path.
- The server (`desktop/capt_runtime_service.serve`) wires `MemoryTriggerEngine`
  and seeds prior-mission memory via `_seed_memory_store`.
