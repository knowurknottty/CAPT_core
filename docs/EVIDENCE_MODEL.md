# Evidence Model (CAPT governed engineering runtime)

This document describes the **Evidence Engine**, **Invalidation Event Model**, and
**proof-preserving reuse** layer implemented in `capt_solo/evidence/`. It is the
operational companion to `docs/VSI_MODEL.md` (Verified State Identity).

VSI answers: *what was proven about a specific repository state?*
Evidence answers: *why is that proof justified, where is the support, does it still apply?*
Invalidation answers: *what concrete event caused a proof to stop applying?*

## Distinct concepts (no collapse into one field)

The system keeps these separate. They are NOT interchangeable:

| Concept | Where it lives | Meaning |
|---|---|---|
| **present** | `EvidenceSource` | observed/recorded right now (tool output, file content) |
| **believed** | `EvidenceRecord` with `evidence_class=USER_DECISION` | asserted by an authority, not yet independently verified |
| **inferred** | `EvidenceClass.DERIVED_INFERENCE` / `SIMULATION_RESULT` | derived; quarantined until corroborated |
| **attempted** | `SelfModificationRecord` (PROPOSED/APPLIED) | an action was tried, outcome pending |
| **changed** | `InvalidationEvent.changed_paths` | a concrete mutation occurred |
| **verified** | `EvidenceStatus.CURRENT` + VSI `verification_current` | a verification run passed at a known state |
| **valid** | `EvidenceStatus.CURRENT` and no active invalidation | currently applicable |
| **invalidated** | `EvidenceStatus.INVALIDATED` + `invalidation_links` | a proof no longer applies due to an event |
| **project-local** | `EvidenceScope.PROJECT` / workspace `.capt/` | bounded to this project; never implicit global |
| **globally-reusable** | `EvidenceScope.GLOBAL` | explicitly promoted across projects (requires approval) |

## Evidence Record (core.py)

`EvidenceRecord` carries: `claim`, `evidence_class`, `source`, `status`,
`scope`, `confidence`, `provenance_chain`, `supersedes`, `invalidated_by`,
`invalidation_links`, `ttl`, `repository_identity`, `project_id`.

Statuses (explicit, never collapsed): `current`, `partial`, `superseded`,
`invalidated`, `quarantined`, `expired`, `unverified`, `conflicted`.

Classes (explicit): `direct_observation`, `tool_output`, `test_result`,
`build_result`, `static_analysis`, `runtime_observation`, `specification`,
`user_decision`, `derived_inference`, `simulation_result`, `external_reference`,
`verification`.

## Invalidation Event Model (invalidation.py)

An `InvalidationEvent` records: `reason`, `changed_paths`, `affected_evidence_ids`,
`unaffected_evidence_ids`, `invalidation_scope`, `required_verification`, `detail`.

Reasons (each maps to a scoped rule):

- `HEAD_CHANGED`, `BRANCH_CHANGED`, `REPOSITORY_CHANGED` → **FULL** (all evidence)
- `DEPENDENCY_LOCKFILE_CHANGED` → **FULL**
- `RUNTIME_IDENTITY_CHANGED`, `ENVIRONMENT_CHANGED` → **FULL**
- `VERIFICATION_POLICY_CHANGED`, `USER_REQUESTED_FRESH` → **FULL**
- `SCOPE_EXPANDED`, `NAMESPACE_CHANGED` → **FULL**
- `SOURCE_EVIDENCE_DELETED`, `SOURCE_EVIDENCE_MODIFIED` → **LOCAL** (affected class)
- `WORKING_TREE_PATH_CHANGED`, `GENERATED_ARTIFACT_CHANGED` → **LOCAL**, scoped by
  path overlap with `EvidenceSource.source_paths` (a docs change does NOT
  invalidate DSP numerical evidence unless an explicit dependency exists)
- `EVIDENCE_SUPERSEDED` → **LOCAL** (same claim)

`scan_invalidation()` is deterministic and does NOT mutate evidence; the caller
applies the status change. `InvalidationGraph.transitive_invalidations()` computes
the closure over a dependency map.

## Proof-preserving reuse (reuse.py + integration.py)

Decision flow (deterministic):

```
existing proof
  -> current state identity (VSI equivalent?)
       -> if equivalent: no invalidator possible from state -> REUSE_CURRENT_EVIDENCE
  -> if changed: scan invalidation
       -> no invalidator for this claim -> REUSE_CURRENT_EVIDENCE (unaffected)
       -> invalidator found -> RUN_TARGETED / RUN_DEPENDENCY / RUN_FULL
  -> no evidence at all -> EVIDENCE_INSUFFICIENT
  -> conflicting evidence -> EVIDENCE_CONFLICTED
```

`EvidenceReuseEngine.decide()` returns a `ReuseOutcome` + `EvidenceDecision`.
Repeated equivalent state does NOT increase confidence and does NOT re-run
verification (anti-loop, no false confidence).

`build_reuse_from_vsi()` converts VSI `VerificationRecord`s into `EvidenceRecord`s
and runs the engine — this is the concrete proof-preserving reuse path that lets a
guard consume a structured decision instead of demanding fresh verification.

## Workspace Isolation (workspace_isolation.py)

`ProjectWorkspace` enforces a bounded project boundary (`.capt/PROJECT_CONTEXT.json`):

- **Unbound** workspace (no context file): no project or global persistence may occur.
- **Bound** workspace: writes scoped to `workspace` / `project_memory` / `global_memory`.
- Path safety rejects traversal (`../`) and symlink escape (resolves realpath and
  verifies it stays within the project root).
- Global memory writes are **never implicit** — they require explicit approval.

## Memory Promotion (promotion.py)

Pipeline: `workspace observation -> candidate -> provenance attached -> evidence
classified -> validate/quarantine -> explicit project promotion`. Global promotion
is a separate, approval-gated step.

Never auto-persisted: stack traces, temp debugging notes, speculative designs, raw
test fixtures, synthetic claims, hidden reasoning, credentials/secrets, raw
biosignal data, unverified completion claims. `DREAM`/simulation/inference outputs
remain labeled and **quarantined** until corroborated. No inferred record may
silently overwrite a verified record.

## Self-Modification Governance (selfmod.py)

Lifecycle: `PROPOSED -> QUARANTINED -> APPROVED -> APPLIED -> VERIFIED ->
REJECTED -> ROLLED_BACK`.

Rules enforced: inspectable diff required to apply; global policy changes
quarantined and require external approval; identical proposals are deduplicated
(anti-loop); per-mission count is capped; rollback path is mandatory; successful
self-editing is never treated as proof of improved behavior.

## Mission Checkpoint & Restart (checkpoint.py)

`MissionCheckpoint` is a compact structured state (no verbose conversation history).
On restart: resolve identity -> load checkpoint -> `detect_divergence` (head/files)
-> `resume_plan` (reuse valid evidence, mark stale assumptions, resume from first
incomplete safe action, avoid replaying completed work). A `completed` mission is
never restarted.

## Long-Session Efficiency (metrics.py)

`AntiLoopGuard` detects repeated verification, reads, failed mutations, blocked
commands, selfmod proposals, promotions, and checkpoints beyond a threshold and
returns a non-progress explanation. `EfficiencyMetrics` tracks reuse count, full
suite runs avoided, targeted runs, invalidations, etc. The goal is maximum verified
progress per unit of execution — not low tool usage.

## CLI surface

- `capt evidence status|show|trace|invalidate|reuse-decision|conflicts`
- `capt mission checkpoint|resume|status`
- `capt selfmod status|propose|diff|rollback`
- `capt verify run --scope X [--force]` / `capt verify status` (VSI)

## Guard contract

A runtime guard should consume the structured decision from
`build_guard_decision()` / `reuse_decision()`:

```json
{
  "state_identity": "equivalent",
  "verification_status": "CURRENT",
  "evidence_status": "CURRENT",
  "invalidation_events": [],
  "action": "reuse_current_evidence",
  "reason": "No relevant state change detected",
  "evidence_record_ids": ["ev-from-v1"],
  "required_verification": []
}
```

When `action == "reuse_current_evidence"`, the guard must NOT demand fresh
verification. This is what prevents verification loops while preserving honesty:
reuse is conditional on an unchanged, un-invalidated state.
