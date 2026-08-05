# CAPT v0.5 composition inventory

Candidate: `3fda86432852fcc238dcd35ecc97e2f415658264`

## Canonical production composition root

`capt_runtime/composition.py:create_runtime()` is the sole canonical construction path for installed operator surfaces. It creates `EventStore`, `RuntimeService`, `DriverRegistry`, `MemoryStore`, and `MemoryTriggerEngine` exactly once. `RuntimeComposition.command_service()` injects its already-created RuntimeService into the existing `RuntimeCommandService`; `RuntimeComposition.openharness_host()` reuses its DriverRegistry and MemoryTriggerEngine.

## Constructor classifications

| Path | Constructors | Classification | Rationale |
|---|---|---|---|
| `capt_runtime/composition.py` | all six requested components | Canonical composition root | Product/operator construction and lifecycle owner. |
| `desktop/capt_runtime_service.py` | none after refactor; uses composition | Intentional wrapper | Authenticated Unix-socket server, query projection, explicit demo seed only. |
| `desktop/m1_command_service.py` | fallback `RuntimeService` only | Intentional wrapper | Backward-compatible isolated-test fallback; production injection uses composition-owned service. |
| `capt_runtime/scenario.py` | EventStore, RuntimeService | Legacy technical debt | Scenario helper predates composition root; not an installed operator surface. |
| `desktop/gate0_activation.py` | EventStore, DriverRegistry, DriverHost | Legacy technical debt | Development activation harness; not packaged operator code. |
| `desktop/acceptance_m1.py`, `desktop/acceptance_m1_live.py` | EventStore, RuntimeService | Legacy technical debt | Acceptance scripts; no installed operator reachability. |
| `tests/**` | all requested components | Test fixture | Isolated contract, adversarial, replay, and integration fixtures. |
| `capt_runtime/store.py`, `services.py`, `drivers/registry.py` | class declarations | Not construction sites | Definitions only. |

## Audit result

No production installed operator surface directly constructs a second RuntimeService, EventStore, DriverRegistry, DriverHost, MemoryStore, or MemoryTriggerEngine after the composition-root packet. Remaining non-test direct construction is explicitly classified as development/acceptance legacy technical debt. No defect requiring a runtime-internal refactor was found in this packet.
