# Human Council Workflow Parity R1

## Mission

A human operator must be able to configure and launch the same governed Council
workflow that previously required a bespoke Python launcher. The UI is a thin
operator surface; RuntimeService/EventStore remains authoritative.

## Acceptance workflow

The reference parity case is the donor-convergence mission:

- cohort 1: `openrouter:qwen/qwen3.8-flash`, 11 logical vessels;
- cohort 2: `openrouter:xiaomi/mimo-v2.6-flash`, 11 logical vessels;
- cohort 3: `openrouter:z-ai/glm-5.3-flash`, 11 logical vessels;
- 33 logical vessels total;
- one provider call per cohort, never one call per logical vessel;
- `maxConcurrentCohorts=1` for sequential mutation of one worktree;
- Deep Vessel Charter v2 for every cohort;
- project-scoped filesystem authority, explicit shell/network/mutation controls;
- one runtime-owned HumanApproval per cohort;
- no automatic approval and no launch until every approval is explicitly approved.

The workflow must remain configurable rather than hard-coded to these three
models. The donor template is an acceptance fixture and convenience preset.
## Human path

Launch the first-class workflow builder:

```zsh
capt-council-workflow \
  --template donor-convergence \
  --target-root /path/to/CAPT_core
```

The operator can edit Council ID, Mission ID, target root, context budget,
execution timeout, concurrency, authority toggles, and each cohort's provider,
model, vessel count, configuration, and objective.

The workflow is a first-class CAPT harness surface. Run `capt council` to open the builder, or `capt council --template donor-convergence --target-root <repo>` to preload the exact 3×11 donor workflow. `capt-council-workflow` remains the direct desktop entrypoint.

The required human sequence is intentionally explicit:

1. Configure or load the workflow.
2. Select **Request approvals**. This creates runtime-owned approval requests only.
3. Inspect the approval rows and choose **Approve requested** or **Deny requested**.
4. Only after every row is authoritative `approved`, choose
   **Launch approved Council**.
5. RuntimeService executes the exact approved Council and returns authoritative
   receipts. The UI cannot manufacture completion or verification.

Draft workflows can be saved and reloaded as JSON. Draft files are convenience
state only; they are never approval authority.
## Runtime path

`capt_ui.operator.council_workflow` validates the human-authored geometry and
builds exact approval intents. `capt_ui.operator.runtime.Operator` submits those
intents through `request_model_prompt_approval`, reads authoritative
`human_approval-*` aggregates, records explicit decisions through
`submit_approval_decision`, and finally calls
`run_approved_council_inspection`.

`run_approved_council_inspection` validates:

- non-empty bounded cohort list;
- unique cohort IDs;
- common vessel count across the Council;
- `1 <= vesselsPerCohort <= 1000`;
- `1 <= maxConcurrentCohorts <= 24`;
- exactly one governed provider execution per cohort.

Each cohort execution delegates to the normal
`run_approved_hermes_inspection` path, so approval consumption, capability
authority, ProviderDriver execution, evidence, task state, and recovery semantics
remain canonical.
## Vessel semantics

`cohortSpec` is approval-bound. The model-visible objective is compiled with the
native cohort contract before the approval digest is created.

Deep Vessel Charter v2 requires a physically countable candidate manifold before
selection, exact selected-vessel rows, source linkage, and an audit row. CAPT
validates the resulting artifact after provider execution. An incomplete
approval-bound charter cannot silently become a completion claim; the task fails
with an explicit cohort-validation result.

Logical vessels remain internal analytical perspectives. They are not additional
provider calls. Cohort concurrency and vessel multiplicity are separate controls.

## Recovery and safety

A UI restart does not recreate authority. Approval state is read from
RuntimeService. Existing DriverRun recovery rules still apply: persisted
indeterminate runs are not blindly redispatched. The workflow surface does not
push, merge, publish, or widen authority by itself.

The UI intentionally has no "request + approve + run" combined action. Human
approval must remain a distinct interaction after the exact approval request has
been materialized.
## Verification gates

The parity implementation is accepted only when all of these are true:

- donor template renders exactly 3 cohorts × 11 vessels;
- provider/model identities match Qwen 3.8 Flash, MiMo 2.6 Flash, and GLM 5.3 Flash;
- sequential launch produces `maxConcurrentCohorts=1`;
- scheduler reports 33 logical vessels and exactly three cohort executions;
- requesting a workflow does not issue any approval decision;
- launch before explicit approval fails closed;
- explicit human approval permits the exact launch payload;
- mixed vessel counts and duplicate cohort IDs fail before runtime dispatch;
- targeted workflow/scheduler tests pass;
- contract drift is clean;
- full CAPT Python suite passes;
- `git diff --check` is clean.

This acceptance replaces the bespoke donor launcher as the proof of human-facing
workflow parity. The older helper may remain as historical/recovery tooling, but
it is no longer required to configure this workflow.
