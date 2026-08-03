# CAPT Memory Trigger Security Review (M1-memory, ADR-DT-M1-MEM-001)

## Adversarial vectors (mission §16 Pass 2)

| Vector | Mitigation | Test |
|---|---|---|
| token estimate accuracy | explicit `ESTIMATED` label + method recorded | `test_estimate_labeled_estimated` |
| threshold off-by-one | boundary uses `ceil`; exact-boundary fires, one-below does not | `test_off_by_one_boundary_does_not_fire`, `test_exactly_on_boundary_fires` |
| duplicate trigger firing | idempotent `TriggerState` per mission | `test_duplicate_trigger_not_re_fired` |
| trigger suppression | no suppression API; gate requires pack | `test_suppression_attempt_has_no_api` |
| Hermes policy override | driver has no policy surface; precedence enforced | `test_driver_cannot_widen_policy` |
| context smuggling | forged `contextPackDigest` rejected (stale) | `test_context_smuggling_rejected_at_dispatch` |
| hidden driver memory | engine never ingests driver memory into policy | `test_hidden_driver_memory_cannot_override` |
| consent leakage | consent gate in `_select_records`; excluded visible | `test_consent_leakage_blocked` |
| stale memory | `stale` flag preserved + labeled | `test_stale_memory_labeled` |
| context growth | boundary recomputed each evaluation | `test_context_growth_recomputes_boundary` |
| incorrect replay | policy log reconstructs exact version | `test_replay_reconstructs_same_policy` |
| configuration race | ledger writes serialized via `threading.Lock` | `test_concurrent_policy_updates_serialized` |
| active-run threshold change | existing pack valid until next rebuild; no invisible change | `test_threshold_change_during_active_run` |
| model-limit mismatch | `validate_policy_steps(max_steps=model_safe_limit)` | `test_model_limit_mismatch_rejected` |
| UI bypass | desktop only submits governed commands; no direct write | `test_ui_bypass_impossible_no_direct_write` |
| stateless fallback | gate refuses dispatch without pack | `test_no_stateless_fallback` |

## Residual risks

- **Token estimate is heuristic** (`chars/4.0`). Exact provider counts would
  tighten the boundary. The estimate is labeled and the confidence is recorded;
  this is acceptable for the mandatory-trigger contract but not a substitute for
  measured tokens when available.
- **Hermes prompt content** is built from the ContextSlice; the slice reference
  is embedded but the driver could in principle ignore it. The driver is
  untrusted and its output is treated as `trust=untrusted`; it cannot alter CAPT
  policy regardless.
- **Memory store is SQLite** (same ledger family). For multi-process CAPT, the
  store would be swapped for the shared ledger; the engine interface is stable.

## No credentials exposed

The memory store contains no secrets. Sensitivity `secret` records are excluded
from the project-scope slice and reported as exclusions. The Hermes environment
is minimized (`minimal_env`) and credential-shaped variables are dropped.
