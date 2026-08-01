# Triple Recursion — Pass 1: Reconstruct Architecture & Repair Foundation

## Inspected files
- `capt_solo/api.py` — public API surface (the ONLY sanctioned import path).
- `capt_solo/runtime.py` — contains `CAPTRuntime`, `RuntimeConfiguration`, `GateDeniedError`.
- `capt_solo/foundry/claimguard.py` — `ClaimGuard.verify_claim`.
- `tests/test_runtime_composition.py`, `tests/test_model_task.py`, `tests/test_model_task_acceptance.py` — the three tests named in the mission.
- `git log --graph` — branch ancestry: `feature/capt-bootstrap-bridge` = merge of `release/capt-v05-layer-reconciliation` (c0f9340) into 65c2255, then 8 bridge commits, then cleanup (648f581).
- `git diff release...feature --stat` — 432 files; PR bundles runtime-skill reconciliation + bridge work (item 13: review scope must be normalized).
- `git ls-remote origin refs/pull/20/head` — PR #20 head = 648f581 (matches local HEAD).

## Confirmed facts
1. The canonical v0.5 composition root **already exists** in `capt_solo/runtime.py` as `CAPTRuntime.load(...)`. It is the single production construction site (docstring: "Single canonical composition root").
2. `CAPTRuntime` owns and shares one set of canonical components: `MemoryEngine`, `CTPRuntime`, `KHSB`, `LifecycleManager`, `ProofEngine`, `CapabilityRegistry`, `ClaimGuard`, `MemoryUseGate`, and a durable event log. `LifecycleManager` receives the same `engine`, `bus`, `ctp` instances; `ProofEngine` and `CapabilityRegistry` use `engine._conn` (no duplicate DB/journal).
3. Each `CAPTRuntime.load()` produces a **distinct `runtime_id`** (uuid4) — verified live.
4. The three required symbols (`CAPTRuntime`, `RuntimeConfiguration`, `GateDeniedError`) were **never absent from the repository** — they were simply **not re-exported from `capt_solo.api`**, which is the only import path the tests use. This is the root cause of the GitHub workflow collection failure (item 2, 3, 4).
5. `test_model_task.py` / `test_model_task_acceptance.py` also import `ModelIdentity`, `ModelTaskRequest`, `ModelTaskResult`, `OpenAICompatibleLocalProvider`, `ProviderError`, `PulseModelProvider` (from `capt_solo.model_task`) and `PulseGateway`, `PulseConfig` (from `capt_solo.pulse`) — all real, all merely unexported from `api`.
6. A second defect: `ClaimGuard.verify_claim` returned `supported=True` for a `verified` capability **without checking the live proof aggregate**. The acceptance test `test_unsupported_claim_verdict` requires `supported=False` when the aggregate is unsatisfiable (2 required, 1 recorded). This was a real correctness bug, not a test-only expectation.

## Assumptions rejected
- "The composition root was lost / never existed." Rejected — it is present in `capt_solo/runtime.py` and matches the test contract exactly (field names, `load()` signature, shared-component assertions).
- "We must invent a new `CAPTRuntime` for the bridge." Rejected — the bridge must launch and verify the canonical runtime, not duplicate it (architectural principle: one canonical composition root).
- "The 2 failing claim-verdict tests are wrong." Rejected — the test correctly encodes the invariant that a claim is only supported when its proof aggregate is satisfied, even for a `verified` capability.

## Defects found
- D1 (item 2/3/4): `capt_solo.api` did not re-export `CAPTRuntime`, `RuntimeConfiguration`, `GateDeniedError`, nor the model-task/pulse public symbols → collection ImportError on 3.10/3.12.
- D2: `ClaimGuard.verify_claim` trusted `lifecycle == "verified"` as sufficient for `supported=True`, bypassing the proof aggregate → incorrect claim verdict.

## Changes made
- `capt_solo/api.py`: re-export `CAPTRuntime`, `RuntimeConfiguration`, `GateDeniedError` from `capt_solo.runtime`; re-export `ModelIdentity`, `ModelTaskRequest`, `ModelTaskResult`, `OpenAICompatibleLocalProvider`, `ProviderError`, `PulseModelProvider` from `capt_solo.model_task`; re-export `PulseConfig`, `PulseGateway` from `capt_solo.pulse`. Added to `__all__`. No aliases, no placeholder classes — only real implementations.
- `capt_solo/foundry/claimguard.py`: when `capability_id` is explicitly provided and a proof aggregate exists, an unsatisfied aggregate now yields `supported=False` even for a `verified` capability. Lifecycle-only support is preserved only when no explicit capability_id aggregate is in play.

## Tests run
- `tests/test_runtime_composition.py` — 9 passed.
- `tests/test_model_task.py` — passed (collection + execution).
- `tests/test_model_task_acceptance.py` — passed (collection + execution).
- Full collection: `pytest tests/ --collect-only` → **913 tests collected, 0 collection errors** (was failing on 3.10/3.12).
- Full suite (excluding the 3 just-fixed modules): 807 passed, 20 failed, 58 skipped. The 20 failures are in **pre-existing, unrelated modules** (`test_distribution_contract`, `test_hermes_capt_core_runtime_skill`, `test_release_identity_option_a`, `test_release_semantics`, `test_v04_cli`, `test_workspace`) and fail identically on the base commit (verified via `git stash` + re-run). They are out of scope for the bridge/runtime reconciliation and are NOT caused by this remediation.

## Unresolved risks
- The 20 pre-existing failures in unrelated modules remain. They are not part of the bridge/runtime reconciliation scope and were failing before this work. They should be triaged separately; forcing them green by weakening tests would violate the mission's "do not weaken/delete tests" rule.
- The bridge's security defects (items 5–12) are addressed in Recursion 2, not here.

## Next-pass objectives (Recursion 2)
- Authenticate the live turn channel (item 5, 6).
- Replace race-prone duplicate-runner lock with atomic lease/fence (item 7, 8).
- Replace plaintext `.sid` sidecar with integrity-bound continuity metadata (item 9–12).
- Strengthen per-turn ownership proof (item: ownership per turn).
- Fix unsafe `except Exception: pass` (item: exception swallowing).
- Harden filesystem/process boundaries.
- Add 28 adversarial tests.
