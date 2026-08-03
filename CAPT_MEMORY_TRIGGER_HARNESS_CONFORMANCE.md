# CAPT Memory Harness Conformance (M1-memory, ADR-DT-M1-MEM-001)

## Scope

Proves memory triggers work with the CAPT reference driver and DriverHost
**without Hermes installed**. The mandatory path is enforced in
`capt_runtime/memory/engine.py` (`require_memory_before_dispatch`) and wired
into `capt_runtime/driver_host.py` (`DriverHost.dispatch`).

## Enforcement points (mission §7)

The engine refuses dispatch when:

| Condition | Code |
|---|---|
| mandatory memory path inactive | `MEMORY_PATH_INACTIVE` |
| ContextPack missing | `CONTEXTPACK_REQUIRED` |
| ContextPack digest invalid / stale | `CONTEXTPACK_STALE` |
| trigger state stale | `CONTEXTPACK_STALE` |
| consent check failed | `MEMORY_CONSENT_DENIED` |
| context exceeds hard-stop boundary | `CONTEXT_BUDGET_EXCEEDED` |
| selected memory violates scope | `MEMORY_SCOPE_VIOLATION` |
| invalid trigger configuration | `MEMORY_TRIGGER_CONFIGURATION_INVALID` |
| rebuild required | `MEMORY_REBUILD_REQUIRED` |

## Harness test matrix (all passing)

- dispatch blocked without ContextPack (`test_dispatch_blocked_without_contextpack`)
- dispatch blocked with stale ContextPack (`test_dispatch_blocked_with_stale_contextpack`)
- dispatch blocked when memory inactive (`test_dispatch_blocked_when_memory_inactive`)
- dispatch blocked when context exceeds hard-stop (`test_dispatch_blocked_when_context_exceeds_hardstop`)
- dispatch blocked on consent failure (`test_dispatch_blocked_on_consent_failure`)
- dispatch blocked on scope violation (`test_dispatch_blocked_on_scope_violation`)
- dispatch allowed with valid pack (`test_dispatch_allowed_with_valid_pack`)
- resume triggers reevaluation (engine state persists per mission)
- verification uses recorded ContextPack (pack digest linked to dispatch gate)
- checkpoint/replay preserves trigger state (`test_reconnect_reconstructs_policy`)

## No stateless fallback

`require_memory_before_dispatch` raises `CONTEXTPACK_REQUIRED` when no pack
exists. There is no raw-prompt dispatch path. See `test_no_stateless_fallback`.

## Evidence

`tests/capt_runtime/test_memory_trigger.py` (43 tests) + adversarial
`test_memory_trigger_adversarial.py` (16 tests).
