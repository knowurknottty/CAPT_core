# Cohort Council Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add configurable multi-model Cohort Councils with up to 10 distinct Cohorts and 111 logical Vessels, governed scheduling, dissent-preserving synthesis, and no conflation of majority with verification.

**Architecture:** UI builds a pure Council definition. RuntimeService validates hard limits/provider-model availability/capabilities/workload ceilings before canonical admission. Vessels are logical perspective/configuration units scheduled under resource/provider concurrency; they are not processes or authority principals. Every external call remains a governed execution record. Council synthesis is an untrusted observation that preserves disagreement.

**Tech Stack:** Python RuntimeService/provider registry/Execution Governor/EventStore; approval/DriverRun concepts; workload budgets; Swift 6/SwiftUI; Human-First Results; pytest/Swift tests.

**Spec:** Parent design §§30-35 and composer parity contract Cohort Council section.

## Global Constraints

- `MAX_DISTINCT_COHORTS = 10`.
- `MAX_LOGICAL_VESSELS = 111`.
- Cohort = provider/model cognitive source.
- Vessel = bounded execution perspective/configuration; Vessel != model/process/authority principal.
- Logical Vessel count != execution concurrency.
- Council majority never creates Verification or ClaimGuard acceptance.
- Minority, abstention, insufficient-evidence, and unresolved positions survive synthesis.
- Each external model call has canonical DriverRun/provenance linkage.
- Council mutation after approval requires a fresh approval.
- Child Vessels inherit, and may narrow but never expand, parent approved scope/capabilities.

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
- current provider/model registry projection.
- `CAPTOperatorStore.swift`
- `ComposerCapabilityMenu.swift`
- `CAPTChatCoordinator.swift`

---

### Task 1: Immutable Council/Cohort/Vessel models and hard limits

**Interfaces:** Python `CouncilDefinition`, `CohortDefinition`, `VesselDefinition`, `validate_council()`; Swift mirrors IDs/limits for UX validation.

- [ ] **Step 1: Write RED hard-limit tests**

```python
from capt_runtime.council import CouncilValidationError, validate_council


def test_rejects_more_than_ten_distinct_cohorts():
    with pytest.raises(CouncilValidationError, match="MAX_DISTINCT_COHORTS"):
        validate_council(make_council(cohort_count=11, vessel_count=11))


def test_allows_111_logical_vessels_but_rejects_112():
    validate_council(make_council(cohort_count=10, vessel_count=111))
    with pytest.raises(CouncilValidationError, match="MAX_LOGICAL_VESSELS"):
        validate_council(make_council(cohort_count=10, vessel_count=112))
```

- [ ] **Step 2: Implement exact Python types/constants**

```python
from dataclasses import dataclass

MAX_DISTINCT_COHORTS = 10
MAX_LOGICAL_VESSELS = 111
SYNTHESIS_MODES = frozenset({"convergent", "debate", "independent_vote", "adversarial_tournament"})

class CouncilValidationError(ValueError): pass

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

`validate_council` enforces non-empty/unique IDs, <=10 Cohorts, <=111 Vessels, distinct `(provider_id, model_id)` Cohort identities, every Vessel cohort ref exists, synthesis mode allowed, optional synthesis Cohort exists, role/instructions bounded and non-empty after trim.

- [ ] **Step 3: Implement Swift mirrors/tests**

Local builder prevents obvious over-limit edits, but RuntimeService validation stays authoritative.

- [ ] **Step 4: Commit**

```bash
git add capt_runtime/council.py tests/capt_runtime/test_council.py capt_ui/surfaces/desktop_swift
git commit -m "feat(council): add cohort and vessel contracts"
```

---

### Task 2: Canonical Council digest and approval binding

**Interfaces:** `council_digest(definition) -> sha256:...`; approval carries `councilId`/`councilDigest` when enabled.

- [ ] **Step 1: Write RED canonicalization/mutation tests**

Reordered input arrays normalize to same digest. Changing Vessel instruction, provider/model, synthesis mode, synthesis Cohort, or membership changes digest.

- [ ] **Step 2: Implement canonical representation**

Sort Cohorts/Vessels by stable ID; JSON sorted keys/compact separators; include stable semantic fields only. Exclude display order/colors, warm latency, provider health.

- [ ] **Step 3: Bind into approval**

Approve Council A then execute Council B -> `MODEL_PROMPT_APPROVAL_COUNCIL_MISMATCH` before parent/child dispatch.

- [ ] **Step 4: Commit**

```bash
git add capt_runtime/model_approval_binding.py capt_runtime/council.py desktop tests
git commit -m "feat(runtime): bind council definition to approval"
```

---

### Task 3: Typed bounded execution planner

**Interfaces:** Produces `VesselScheduleItem`, `CouncilWave`, `CouncilExecutionPlan`, `plan_council()`.

- [ ] **Step 1: Write RED concurrency test**

```python
def test_111_vessels_do_not_imply_111_concurrency():
    p = plan_council(
        make_council(10, 111),
        provider_available=all_available,
        provider_concurrency={"mtplx": 1, "remote": 4},
        global_max_concurrency=4,
    )
    assert p.logical_vessel_count == 111
    assert p.global_max_concurrency == 4
    assert max(len(w.items) for w in p.waves) <= 4
```

- [ ] **Step 2: Implement exact schedule types**

```python
@dataclass(frozen=True)
class VesselScheduleItem:
    vessel_id: str
    cohort_id: str
    provider_id: str
    model_id: str
    ordinal: int

@dataclass(frozen=True)
class CouncilWave:
    wave_index: int
    items: tuple[VesselScheduleItem, ...]

@dataclass(frozen=True)
class CouncilExecutionPlan:
    council_id: str
    council_digest: str
    logical_vessel_count: int
    global_max_concurrency: int
    waves: tuple[CouncilWave, ...]
```

- [ ] **Step 3: Implement deterministic wave planner**

Validate first. Sort Vessels by stable `vessel_id`; greedily fill each wave up to `global_max_concurrency` while not exceeding per-provider concurrency. Provider unavailable/missing model rejects planning before admission. `(provider,model)` duplicate Cohort identity is invalid from Task 1.

For current MTPLX serial endpoint, provider concurrency input is 1. This is configuration/resource policy, not a hard-coded special case inside generic planner.

- [ ] **Step 4: Add impossible-policy test**

`global_max_concurrency < 1` or provider concurrency <1 for a referenced provider rejects rather than creating empty/infinite scheduling loops.

- [ ] **Step 5: Commit**

```bash
git add capt_runtime/council.py tests/capt_runtime/test_council.py
git commit -m "feat(council): plan bounded vessel execution"
```

---

### Task 4: Native Council builder without dispatch authority

**Interfaces:** Add/remove <=10 Cohorts, <=111 Vessels, assign Vessel->Cohort, role/instructions, synthesis mode/cohort.

- [ ] **Step 1: Write builder state tests**

Cohort #11/Vessel #112 yields local validation error with existing definition unchanged. Removing a Cohort with assigned Vessels requires explicit reassignment/removal.

- [ ] **Step 2: Implement builder**

Display `Cohorts n/10`, `Vessels n/111`. Cohort picker reads live provider/model registry. Vessel editor shows role/instructions/Cohort. Plain-language secondary text explains Cohort vs Vessel.

- [ ] **Step 3: Implement exact synthesis controls**

Convergent adjudication, Debate, Independent vote, Adversarial tournament. Optional synthesis Cohort may prefill from primary selected model but is explicitly saved in Council definition.

- [ ] **Step 4: Persistence semantics**

`Save to Project` writes Council defaults through Project store. Otherwise Council remains per-chat/composer draft. Both are ledger-neutral.

- [ ] **Step 5: Commit**

```bash
git add capt_ui/surfaces/desktop_swift
git commit -m "feat(mac): add cohort council builder"
```

---

### Task 5: RuntimeService governed parent admission + child Vessel executions

**Interfaces:** One approved Council execution creates canonical parent plan intent and linked governed child DriverRuns.

- [ ] **Step 1: Write RED lifecycle test: 2 Cohorts / 3 Vessels**

Approval/admission binds parent Council digest. Each dispatched Vessel has unique DriverRun + parent Council/task reference + Cohort/Vessel provenance. No Vessel observation is Verification.

- [ ] **Step 2: Implement immutable preparation/admission**

Prepare/validate entire CouncilExecutionPlan before consuming approval. Admission persists parent execution identity/digest before any child external boundary. Child schedule is derived from the admitted immutable plan, not re-read UI state.

- [ ] **Step 3: Execute waves using canonical DriverRun semantics**

For each item, RuntimeService creates/adopts the canonical child run path, capability/resource reservation, dispatch, observation/evidence recording, and finalization. Scope inherits/narrows parent approved scope.

- [ ] **Step 4: Preserve failure isolation/partial results**

One Vessel failure marks that Vessel failed/abstained according to result reason and does not erase successful siblings. Exhausted wall-clock/cost/provider ceiling leaves undispatched Vessel IDs in explicit partial state.

- [ ] **Step 5: Add restart/no-repeat test**

Crash after A complete/B running: A never repeats; B follows persisted indeterminate reconciliation; undispatched C may continue only from admitted parent plan under remaining resource policy. No UI reconstruction or new model choice occurs.

- [ ] **Step 6: Commit**

```bash
git add capt_runtime desktop tests
git commit -m "feat(runtime): execute governed cohort councils"
```

---

### Task 6: Typed dissent-preserving Council result

**Interfaces:** Produces `VesselObservation`, `CouncilAgreementGroup`, `CouncilResult`.

- [ ] **Step 1: Write RED conflict test**

Two Vessels support A, one supports B. Result contains both groups. No verified flag/status is derived from 2/3 agreement.

- [ ] **Step 2: Implement exact result types**

```python
@dataclass(frozen=True)
class VesselObservation:
    vessel_id: str
    cohort_id: str
    driver_run_id: str
    statement: str
    evidence_refs: tuple[str, ...]
    disposition: str  # observed | failed | abstained | insufficient_evidence

@dataclass(frozen=True)
class CouncilAgreementGroup:
    normalized_statement_digest: str
    statement: str
    supporting_vessel_ids: tuple[str, ...]
    contradicting_vessel_ids: tuple[str, ...]

@dataclass(frozen=True)
class CouncilResult:
    council_id: str
    observations: tuple[VesselObservation, ...]
    agreement_groups: tuple[CouncilAgreementGroup, ...]
    abstained_vessel_ids: tuple[str, ...]
    failed_vessel_ids: tuple[str, ...]
    unresolved_group_digests: tuple[str, ...]
    synthesis_observation: VesselObservation | None
    verification_id: str | None
```

Council aggregation always initializes `verification_id=None`; only a separate VerificationPipeline action may produce one.

- [ ] **Step 3: Aggregate before synthesis**

Group normalized claim statements/digests preserving all source Vessel IDs/evidence refs. Agreement count is descriptive only.

- [ ] **Step 4: Synthesis remains another governed observation**

Synthesis Cohort receives bounded observations/groups and instruction to report converged, minority, abstained/insufficient, unresolved positions. Its output is stored as `synthesis_observation`, not promoted to truth.

- [ ] **Step 5: Human-first rendering**

Default card shows agreement/dissent counts and sections; Raw details exposes Vessel/Cohort/DriverRun provenance.

- [ ] **Step 6: Commit**

```bash
git add capt_runtime capt_ui/surfaces/desktop_swift tests
git commit -m "feat(council): preserve dissent in council synthesis"
```

---

### Task 7: Council authority/resource/security gates

**Interfaces:** Every child respects provider credentials/classification, workload/cost ceilings, and parent Project/workspace/file capabilities.

- [ ] **Step 1: Unauthorized scope test**

Vessel attempts filesystem/workspace/file expansion beyond parent approval -> rejection before child dispatch.

- [ ] **Step 2: Resource ceiling test**

Budget expires before all scheduled calls -> stop before exceeding ceiling; explicit partial `undispatched_vessel_ids`; no fabricated results.

- [ ] **Step 3: Provider-loss test**

Provider unavailable after planning but before dispatch -> affected Vessel unavailable/failed with evidence; no silent substitution.

- [ ] **Step 4: Commit**

```bash
git add capt_runtime desktop tests
git commit -m "test(council): harden council authority and resource limits"
```

---

### Task 8: Council acceptance

- [ ] Limits: 1C/1V, 10C/111V, reject 11C, reject 112V, invalid Vessel->Cohort, duplicate Cohort identity.
- [ ] Scheduling: MTPLX concurrency input 1; overall Council may use other provider slots within global policy; never > configured limits.
- [ ] Dissent: controlled conflicting observations preserve minority/unresolved; `verification_id` stays `None` until separate verification.
- [ ] Restart: completed child DriverRuns never repeat.
- [ ] Authority: child scopes cannot expand parent scope; Council config edits alone are ledger-neutral.
- [ ] Run full Python suite, Swift tests, and `swift build --product CAPTNativeMac` with zero failures.
