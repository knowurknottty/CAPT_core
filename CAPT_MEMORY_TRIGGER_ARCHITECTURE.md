# CAPT Memory Trigger Architecture (M1-memory, ADR-DT-M1-MEM-001)

## Status

`CAPT_MEMORY_TRIGGER_PROVEN` — mandatory memory is active, the 32k-step
configuration works, harness conformance passes, genuine Hermes conformance
passes, the Desktop control works, the ContextPack is mandatory, trigger state
persists and replays, no stateless fallback exists, promotion is governed, and
exact-SHA evidence exists (see `CAPT_MEMORY_TRIGGER_VERIFICATION_REPORT.md`).

## Authoritative flow (no cognitive module may bypass)

```
Mission received
→ context and memory budget established      (MemoryTriggerEngine + MemoryTriggerPolicy)
→ current context usage measured             (ContextAccounting.estimate / measure)
→ next 32k trigger boundary calculated        (ContextAccounting.next_trigger_boundary)
→ governed memory query executed              (build_memory_query -> MemoryStore.query)
→ records selected / excluded                (_select_records, consent + sensitivity gates)
→ ContextPack assembled                       (build_context_pack)
→ ContextPack digest recorded                 (ContextPack.contextPackDigest = sha256(...))
→ bounded slice dispatched to driver          (DriverHost.dispatch -> require_memory_before_dispatch)
→ execution observations returned            (HermesDriver.submit -> untrusted observation)
→ memory promotion evaluated                 (MemoryTriggerEngine.evaluate_promotion)
→ checkpoint persisted                        (EventStore + memory ledger)
→ next trigger recalculated                   (evaluate_usage)
```

## Ownership

CAPT owns the trigger decision. The runtime `MemoryTriggerEngine`
(`capt_runtime/memory/engine.py`) is the single owner. Drivers and the desktop
consume the resulting ContextPack slice and policy reference; they never call
the trigger decision and never write memory policy.

## Components

| Component | Path | Role |
|---|---|---|
| `MemoryTriggerPolicy` | `capt_runtime/memory/policy.py` | 32k-step ladder, precedence, validation |
| `ContextAccounting` | `capt_runtime/memory/accounting.py` | usage measurement, next-boundary math |
| `MemoryStore` | `capt_runtime/memory/store.py` | SQLite record store, consent/sensitivity gates |
| `build_memory_query` | `capt_runtime/memory/query.py` | typed MemoryQuery contract |
| `build_context_pack` | `capt_runtime/memory/contextpack.py` | idempotent ContextPack + digest |
| `MemoryTriggerEngine` | `capt_runtime/memory/engine.py` | trigger state, dispatch gate, promotion, replay |
| `DriverHost.dispatch` | `capt_runtime/driver_host.py` | mandatory gate before every driver dispatch |
| `HermesDriver` | `capt_runtime/drivers/hermes.py` | real external driver; receives only the slice |
| `RuntimeCommandService` | `desktop/m1_command_service.py` | `update_memory_trigger_policy` command |
| `DesktopApp` | `desktop/desktop_app.py` | operator trigger controls (Tab 5) |

## Trigger types (independent 32k steps)

`retrieval`, `compression`, `checkpoint`, `consolidation`, `hardStop`. Each has
its own step count. Default effective policy (model safe limit = 8 steps =
262,144 tokens): all triggers = 8 steps. Operator may narrow; cannot widen past
the model safe limit.

## Contracts

`MemoryTriggerPolicy`, `MemoryQuery`, `MemoryRecord`, `ContextPack` added to
`contracts/schema/common.schema.json`. `ContextSlice.contextPackRef` and
`ExecutionDriverWorkOrder.memoryPolicyRef` added to
`contracts/schema/driver.schema.json`. All regenerated and drift-clean.

## Precedence

```
constitutional > runtime_policy > model_provider > project_policy
> operator_selected > driver_preference
```

A lower-authority layer may narrow but not widen a higher-authority bound.
Hermes (driver_preference) cannot increase the configured safe limit.

## Evidence

- Tests: `tests/capt_runtime/test_memory_trigger.py` (43), `..._hermes.py`
  (10, real Hermes dispatch), `..._desktop.py` (5), `..._adversarial.py` (16).
- Runtime smoke: `desktop/capt_runtime_service.serve` wires the engine; the
  `UpdateMemoryTriggerPolicy` command and `get_memory_policy` / `get_memory_state`
  queries are exercised end-to-end.
