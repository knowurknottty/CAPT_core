# Cohort Council Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add configurable multi-model Cohort Councils with up to 10 distinct Cohorts and 111 logical Vessels, governed scheduling, dissent-preserving synthesis, and no conflation of majority with verification.

**Architecture:** The UI builds a pure Council definition. RuntimeService validates hard limits, provider/model availability, capability requirements, and workload ceilings before creating execution work. Vessels are logical perspective/configuration units scheduled under Execution Governor concurrency; they are not processes and do not mint authority. Council observations remain evidence; synthesis records agreement/disagreement without auto-verification.

**Tech Stack:** Python RuntimeService/provider registry/Execution Governor/EventStore; existing approval and DriverRun concepts; Swift 6/SwiftUI builder; ResultPresentation; workload budgets; pytest/Swift tests.

**Spec:** Parent design §§30-35 and composer parity contract Cohort Council section.

## Global Constraints

- `MAX_DISTINCT_COHORTS = 10`.
- `MAX_LOGICAL_VESSELS = 111`.
- Cohort is a model/provider cognitive source.
- Vessel is a bounded execution perspective/configuration; Vessel != model/process/authority principal.
- Logical Vessel count and execution concurrency are different limits.
- Council majority does not create Verification/ClaimGuard acceptance.
- Minority findings and abstentions/insufficient-evidence positions survive synthesis.
- Every external model call is still a governed DriverRun/equivalent canonical execution record.
- Council definition mutation after approval requires a fresh approval.

## File Structure

**Create:**
- `capt_runtime/council.py`
- `tests/capt_runtime/test_council.py`
- `CAPTCoreDesktop/CAPTCouncilModels.swift`
- `CAPTNativeMac/Views/CouncilBuilderView.swift`
- `CAPTNativeMac/Views/CouncilResultView.swift`
- `CAPTCoreDesktopTests/CAPTCouncilModelsTests.swift`

**Modify:**
- `capt_runtime/model_approval_binding.py`
- `desktop/capt_runtime_service.py`
- provider/model registry projection used by native app.
- `CAPTOperatorStore.swift`
- `ComposerCapabilityMenu.swift`
- `CAPTChatCoordinator.swift`

---

### Task 1: Council/Cohort/Vessel immutable models and hard limits

**Interfaces:**
- Python: `CouncilDefinition`, `CohortDefinition`, `VesselDefinition`, `validate_council()`.
- Swift mirrors the same stable identifiers/limits for local UX validation.

- [ ] **Step 1: Write RED Python hard-limit tests**

```python
from capt_runtime.council import CouncilValidationError, validate_council


def test_rejects_more_than_ten_distinct_cohorts():
    council = make_council(cohort_count=11, vessel_count=11)
    with pytest.raises(CouncilValidationError, match="MAX_DISTINCT_COHORTS"):
        validate_council(council)


def test_allows_111_logical_vessels_but_rejects_112():
    validate_council(make_council(cohort_count=10, vessel_count=111))
    with pytest.raises(CouncilValidationError, match="MAX_LOGICAL_VESSELS"):
        validate_council(make_council(cohort_count=10, vessel_count=112))
```

- [ ] **Step 2: Implement Python dataclasses/constants**

```python
MAX_DISTINCT_COHORTS = 10
MAX_LOGICAL_VESSELS = 111

@dataclass(frozen=True)
class CohortDefinition:
    cohort_id: str
    provider_id: str
    model_id: str

@dataclass(frozen=True)
class VesselDefinition:
    vessel_id: str
    cohort_id: str
    role: str
    instructions: str

@dataclass(frozen=True)
class CouncilDefinition:
    council_id: str
    cohorts: tuple[CohortDefinition, ...]
    vessels: tuple[VesselDefinition, ...]
    synthesis_mode: str
    synthesis_cohort_id: str | None
```

Validate unique IDs, Vessel cohort references, distinct provider/model identities, allowed synthesis modes: `convergent`, `debate`, `independent_vote`, `adversarial_tournament`.

- [ ] **Step 3: Implement Swift mirrors and tests**

Local UI prevents obvious over-limit configuration but RuntimeService validation remains authoritative.

- [ ] **Step 4: Commit**

```bash
git add capt_runtime/council.py tests/capt_runtime/test_council.py capt_ui/surfaces/desktop_swift
git commit -m "feat(council): add cohort and vessel contracts"
```

---

### Task 2: Council digest and approval binding

**Interfaces:**
- Produces `council_digest(definition) -> sha256:...`.
- Approval binding carries `councilId` and exact `councilDigest` when Council mode is enabled.

- [ ] **Step 1: Write RED canonicalization/mutation tests**

Same Council with different input array ordering normalizes to one digest after sorting by stable IDs. Changing a Vessel instruction, model, synthesis mode, or membership changes digest.

- [ ] **Step 2: Implement canonical digest**

Canonical JSON contains stable IDs/provider/model/role/instructions/synthesis only. Exclude display colors, UI ordering, warm latency, and transient provider health.

- [ ] **Step 3: Bind into approval**

Approve Council A then offer Council B to execution; reject before any child DriverRun creation.

- [ ] **Step 4: Commit**

```bash
git add capt_runtime desktop tests
git commit -m "feat(runtime): bind council definition to approval"
```

---

### Task 3: Provider/model availability and resource-plan validation

**Interfaces:**
- Produces `CouncilExecutionPlan` with logical Vessel queue and max concurrency.

- [ ] **Step 1: Write RED resource tests**

```python
def test_111_vessels_do_not_imply_111_concurrency():
    p = plan_council(make_council(10, 111), max_concurrency=4)
    assert p.logical_vessel_count == 111
    assert p.max_concurrency == 4
    assert len(p.waves) >= 28
```

Test missing provider/model rejects before admission; duplicate Cohorts using identical provider/model identity reject as not distinct.

- [ ] **Step 2: Implement planner**

Inputs: validated Council, provider registry snapshot, workload profile, Execution Governor/resource ceiling. Output immutable ordered Vessel schedule/waves. Default local max concurrency must be conservative and derive from resource policy, never `len(vessels)`.

- [ ] **Step 3: Add local-provider serialization rule where required**

For MTPLX current serial server configuration, planner max concurrency for that provider is 1 even if overall Council concurrency is higher; other remote providers may occupy other slots according to policy.

- [ ] **Step 4: Commit**

```bash
git add capt_runtime/council.py tests/capt_runtime/test_council.py
git commit -m "feat(council): plan bounded vessel execution"
```

---

### Task 4: Native Council builder UI without dispatch

**Interfaces:**
- User can add/remove up to 10 Cohorts and up to 111 Vessels, assign Vessel->Cohort, role/instructions, synthesis mode/cohort.

- [ ] **Step 1: Write Swift builder state tests**

Attempt Cohort #11 and Vessel #112 -> local validation error; existing definition unchanged. Removing a Cohort with assigned Vessels requires explicit reassignment/removal rather than silently orphaning them.

- [ ] **Step 2: Implement `CouncilBuilderView`**

Display counts `Cohorts n/10`, `Vessels n/111`. Cohort picker reads live provider/model registry. Vessel editor exposes role/instructions and Cohort association. Explain Cohort/Vessel in tooltips/plain-language secondary copy.

- [ ] **Step 3: Add synthesis controls**

Modes exactly: Convergent adjudication, Debate, Independent vote, Adversarial tournament. Optional synthesis Cohort defaults to primary selected model when valid but remains explicit in the saved definition.

- [ ] **Step 4: Save Council definitions locally**

Store in Project defaults when user chooses `Save to Project`; otherwise retain per-chat/composer draft. No RuntimeService ledger mutation.

- [ ] **Step 5: Commit**

```bash
git add capt_ui/surfaces/desktop_swift
git commit -m "feat(mac): add cohort council builder"
```

---

### Task 5: RuntimeService governed Council admission and child executions

**Interfaces:**
- One approved Council request produces a canonical parent task/plan and governed child Vessel executions linked to parent Council ID.

- [ ] **Step 1: Write RED lifecycle test with two Cohorts/three Vessels**

Assert approval -> admission creates canonical parent execution intent; each dispatched Vessel receives its own DriverRun identity/provenance. No Vessel output is automatically verification.

- [ ] **Step 2: Implement Council runner inside RuntimeService composition**

Prepare full immutable Council plan before consuming approval. Admission atomically binds parent Council digest/intent. Scheduler dispatches child work according to waves/resource leases. On restart, persisted child DriverRun states follow existing no-repeat/reconciliation semantics.

- [ ] **Step 3: Preserve failure isolation**

One Vessel failure yields failed/abstained Vessel result and does not silently cancel successful siblings unless policy says fail-fast. Exhausted provider/time/resource budget becomes an explicit Council partial-result state.

- [ ] **Step 4: Add restart test**

Crash after child A completion and child B running; on recovery, A is not repeated, B follows persisted indeterminate reconciliation, remaining undispatched Vessels resume only if parent task/policy permits and no approval replay is required beyond the already admitted parent plan.

- [ ] **Step 5: Commit**

```bash
git add capt_runtime desktop tests
git commit -m "feat(runtime): execute governed cohort councils"
```

---

### Task 6: Dissent-preserving synthesis and result envelope

**Interfaces:**
- Produces `CouncilResult` with per-Vessel observations, agreement groups, dissent, abstentions, unresolved conflicts, synthesis observation, verification state separate.

- [ ] **Step 1: Write RED conflict test**

Three Vessels: two say A, one says B with cited evidence. Assert result contains majority group A and minority group B; no `verified=true` field appears solely because 2/3 agree.

- [ ] **Step 2: Implement aggregation before synthesis**

Group claims by normalized statement/digest relation, preserving source Vessel IDs and evidence refs. `agreementCount` is descriptive only.

- [ ] **Step 3: Implement synthesis prompt/context**

Synthesis Cohort receives all bounded observations plus explicit instruction to report converged, minority, abstained/insufficient-evidence, and unresolved findings. Synthesis itself is another untrusted observation.

- [ ] **Step 4: Integrate with Human-First Results**

Default card:

```text
7/10 cohorts agree
2 disagree
1 insufficient evidence

Converged findings
Minority findings
Unresolved conflicts
```

Technical/raw disclosure contains Vessel/DriverRun IDs and provenance.

- [ ] **Step 5: Commit**

```bash
git add capt_runtime capt_ui/surfaces/desktop_swift tests
git commit -m "feat(council): preserve dissent in council synthesis"
```

---

### Task 7: Council capability/resource/security gates

**Interfaces:**
- Each Cohort/provider call must respect provider credentials, local/remote classification, workload/time ceilings, and project/workspace/file capabilities inherited from the approved parent execution.

- [ ] **Step 1: Write unauthorized-context test**

A Vessel cannot expand filesystem/workspace/file scope beyond the parent approved execution. Attempted scope mutation rejects before child dispatch.

- [ ] **Step 2: Write cost/resource ceiling test**

Set Council budget lower than total requested calls; planner/runtime stops before exceeding ceiling and returns partial Council state with undispatched Vessel IDs.

- [ ] **Step 3: Write provider-loss test**

Provider disappears after planning but before its Vessel dispatch: mark affected Vessel unavailable; do not substitute another provider/model silently.

- [ ] **Step 4: Commit**

```bash
git add capt_runtime desktop tests
git commit -m "test(council): harden council authority and resource limits"
```

---

### Task 8: Council acceptance

- [ ] **Step 1: Limit matrix**

Validate 1C/1V, 10C/111V, 11C rejection, 112V rejection, invalid Vessel->Cohort reference, duplicate Cohort identity.

- [ ] **Step 2: Local scheduling proof**

With MTPLX + remote cohorts, prove MTPLX Vessel calls serialize at provider concurrency 1 while overall Council can execute other provider slots within policy.

- [ ] **Step 3: Dissent proof**

Construct controlled conflicting outputs; result preserves minority/unresolved state and `verificationId` remains absent until separate VerificationPipeline action.

- [ ] **Step 4: Restart/no-repeat proof**

Prove persisted completed child DriverRuns are never repeated after restart.

- [ ] **Step 5: Full suites/build**

```bash
python -m pytest -q
cd capt_ui/surfaces/desktop_swift
swift test
swift build --product CAPTNativeMac
```
