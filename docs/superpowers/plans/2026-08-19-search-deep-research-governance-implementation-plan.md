# Search + Deep Research Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add distinct Search and Deep Research execution modes with explicit governed wall-clock/retrieval budgets so long-form work can complete without globally weakening CAPT's interactive timeout discipline.

**Architecture:** Introduce immutable workload profiles in RuntimeService admission. The approval binding carries `workloadProfileId`; the effective wall-clock/retrieval ceilings are computed before dispatch and become cognitive/execution provenance. Search remains a bounded retrieval path. Deep Research executes decomposition/retrieval/evidence/adversarial/synthesis stages under one governed research plan rather than a prompt suffix.

**Tech Stack:** Python CAPT RuntimeService/EventStore, provider driver, ContextPack/evidence pipeline, existing approval binding, web/retrieval adapters where configured, Swift composer mode selection/result rendering, pytest/Swift tests.

**Spec:** Parent design Part IV §§26-29 plus composer parity contract Search/Deep Research sections.

## Global Constraints

- Existing ordinary interactive chat remains bounded; do not globally replace 120 seconds with a large timeout.
- Workload profile is bound at approval and cannot be changed after approval without a fresh approval.
- Token context limit and wall-clock budget are separate dimensions.
- Deep Research results remain evidence/analysis until verification; source count/majority is not truth.
- Retrieval source provenance and timestamp are recorded.
- Search is distinct from Deep Research.
- No network access is silently granted to local file scanners or unrelated capabilities by enabling research.

## File Structure

**Create:**
- `capt_runtime/workload_budget.py`
- `capt_runtime/research.py`
- `tests/capt_runtime/test_workload_budget.py`
- `tests/capt_runtime/test_research_plan.py`
- `CAPTCoreDesktop/CAPTResearchModels.swift`
- `CAPTCoreDesktopTests/CAPTResearchModelsTests.swift`

**Modify:**
- `capt_runtime/model_approval_binding.py`
- `capt_runtime/operator_provenance.py`
- `desktop/capt_runtime_service.py`
- provider driver timeout plumbing where the current hard 120-second value is applied.
- `CAPTChatCoordinator.swift` to include workload profile ID selected by composer.
- `CAPTOperatorStore.swift` to project current mode/status.

---

### Task 1: Workload profile contract

**Interfaces:**
- Produces `WorkloadProfile` and `resolve_workload_profile(profile_id, provider_context_limit)`.

- [ ] **Step 1: Write RED profile tests**

```python
from capt_runtime.workload_budget import resolve_workload_profile


def test_interactive_profile_remains_bounded():
    p = resolve_workload_profile("interactive_chat")
    assert p.wall_seconds == 120
    assert p.max_retrieval_rounds == 0


def test_deep_research_has_explicit_larger_budget_not_global_override():
    p = resolve_workload_profile("deep_research")
    assert p.wall_seconds == 600
    assert p.max_retrieval_rounds == 8
```

- [ ] **Step 2: Implement immutable profiles**

```python
@dataclass(frozen=True)
class WorkloadProfile:
    profile_id: str
    wall_seconds: int
    max_retrieval_rounds: int
    max_sources: int
    max_parallel_provider_calls: int
    purpose: str

PROFILES = {
    "interactive_chat": WorkloadProfile("interactive_chat", 120, 0, 0, 1, "ordinary interactive chat"),
    "search": WorkloadProfile("search", 180, 2, 12, 2, "bounded sourced retrieval"),
    "deep_research": WorkloadProfile("deep_research", 600, 8, 64, 4, "multi-stage governed research"),
    "code_review_deep": WorkloadProfile("code_review_deep", 300, 0, 0, 1, "long-context code analysis"),
}
```

These are initial release ceilings; changing them is a policy/config change, not an implicit provider behavior.

- [ ] **Step 3: Add invalid-profile rejection tests**

Unknown IDs must reject before dispatch; no fallback to interactive profile for an explicitly unknown value.

- [ ] **Step 4: Commit**

```bash
git add capt_runtime/workload_budget.py tests/capt_runtime/test_workload_budget.py
git commit -m "feat(runtime): add governed workload budgets"
```

---

### Task 2: Bind profile to approval and provenance

**Interfaces:**
- Approval binding gains exact `workloadProfileId` and resolved budget digest/fields.
- Cognitive provenance exposes requested/effective wall-clock budget.

- [ ] **Step 1: Write RED mutation test**

Approve `interactive_chat`; execute as `deep_research` using same approval ID. Expect `MODEL_PROMPT_APPROVAL_WORKLOAD_MISMATCH`, zero external dispatch.

- [ ] **Step 2: Extend approval binding**

Include `workloadProfileId` in deterministic execution binding and prepared execution digest. Resolve profile during preparation; freeze effective budget into prepared data.

- [ ] **Step 3: Extend provenance**

Add:

```json
{
  "workloadProfileId": "deep_research",
  "effectiveWallClockSeconds": 600,
  "maxRetrievalRounds": 8,
  "maxSources": 64
}
```

Do not claim the full budget was consumed; these are ceilings.

- [ ] **Step 4: Commit**

```bash
git add capt_runtime desktop tests
git commit -m "feat(runtime): bind workload profile to model approval"
```

---

### Task 3: Provider timeout uses admitted profile

**Interfaces:**
- Provider driver receives `timeout_seconds` from prepared execution, not a hidden global constant.

- [ ] **Step 1: Write RED driver timeout propagation test**

Inject a fake provider transport and assert `interactive_chat` receives 120 and `code_review_deep` receives 300.

- [ ] **Step 2: Thread the frozen timeout through the driver call**

Do not read current UI preference/provider state again after admission. The timeout is part of immutable prepared execution.

- [ ] **Step 3: Add timeout classification test**

A provider timeout must remain a typed `PROVIDERDRIVERFAILURE`/timeout detail, and DriverRun/task recovery semantics remain unchanged.

- [ ] **Step 4: Re-run the previously observed long-context scenario**

Use the same ~10K-token code-review dossier. Under `interactive_chat` it may hit 120s; under `code_review_deep` it must be admitted with 300s and allowed to complete if the provider returns within that ceiling. Record actual elapsed time separately from ceiling.

- [ ] **Step 5: Commit**

```bash
git add capt_runtime desktop tests
git commit -m "fix(runtime): enforce admitted provider wall-clock budget"
```

---

### Task 4: Search research-plan model

**Interfaces:**
- Produces `ResearchPlan`, `ResearchSourceRecord`, `ResearchClaimRecord`.

- [ ] **Step 1: Write RED plan tests**

```python
def test_search_plan_is_bounded():
    p = ResearchPlan.for_mode("search", "current GPU rental pricing")
    assert len(p.stages) <= 3
    assert p.max_sources == 12


def test_deep_research_plan_contains_adversarial_stage():
    p = ResearchPlan.for_mode("deep_research", "question")
    assert [s.kind for s in p.stages] == [
        "decompose", "retrieve", "claim_map", "adversarial_check", "synthesize"
    ]
```

- [ ] **Step 2: Implement deterministic plan templates**

Search stages: `retrieve -> source_check -> synthesize`.

Deep Research stages: `decompose -> retrieve -> claim_map -> adversarial_check -> synthesize`.

Each stage carries stage ID, purpose, input refs, source/retrieval budget, and completion state. Do not put source truth judgments into the planner.

- [ ] **Step 3: Commit**

```bash
git add capt_runtime/research.py tests/capt_runtime/test_research_plan.py
git commit -m "feat(research): add governed search and deep research plans"
```

---

### Task 5: Retrieval/source provenance and evidence graph

**Interfaces:**
- Each retrieved source produces `ResearchSourceRecord(source_id, url, retrieved_at, content_digest, provider, title)`.
- Claim map links claim IDs to supporting/contradicting source IDs.

- [ ] **Step 1: Write RED provenance tests**

Two snapshots from the same URL at different retrieval times/digests remain distinct records. A claim with conflicting sources records both rather than deleting the minority source.

- [ ] **Step 2: Implement source registry and claim map**

Canonical URL + retrieval timestamp + digest are stored. Keep excerpts within configured copyright/source constraints in presentation layers; internal provenance stores digests/metadata and bounded excerpts as policy permits.

- [ ] **Step 3: Implement adversarial check stage**

Require at least one of: contradictory source search, source-authority challenge, temporal-staleness check, or missing-evidence determination for each high-impact claim. An inability to resolve conflict becomes `unresolved`, not forced consensus.

- [ ] **Step 4: Commit**

```bash
git add capt_runtime/research.py tests/capt_runtime/test_research_plan.py
git commit -m "feat(research): preserve source and claim provenance"
```

---

### Task 6: Native Search / Deep Research mode binding

**Interfaces:**
- Composer `.search` maps to workload profile `search`.
- `.deepResearch` maps to `deep_research`.
- Normal maps to `interactive_chat`, except explicit deep-code-review controls may choose `code_review_deep` later.

- [ ] **Step 1: Write Swift mapping tests**

```swift
#expect(CAPTExecutionMode.search.workloadProfileID == "search")
#expect(CAPTExecutionMode.deepResearch.workloadProfileID == "deep_research")
#expect(CAPTExecutionMode.normal.workloadProfileID == "interactive_chat")
```

- [ ] **Step 2: Add mode chip/status**

Search and Deep Research are mutually exclusive. The user can remove the chip before Send, returning to Normal.

- [ ] **Step 3: Display research progress human-readably**

Stages appear as `Searching sources`, `Checking claims`, `Synthesizing` rather than raw event JSON. Raw stage envelopes remain available in Raw details.

- [ ] **Step 4: Commit**

```bash
git add capt_ui/surfaces/desktop_swift
git commit -m "feat(mac): bind research modes to governed workload profiles"
```

---

### Task 7: Search + Deep Research acceptance

- [ ] **Step 1: Approval-binding acceptance**

Attempt profile mutation after approval; confirm rejection and zero dispatch.

- [ ] **Step 2: Timeout acceptance**

Demonstrate ordinary chat retains 120-second ceiling; deep code review can use 300; Deep Research can use 600. Record actual elapsed time and outcome.

- [ ] **Step 3: Source provenance acceptance**

Run Search against a changing/current topic; confirm source URL, retrieval time, digest, and source relation to claims are retained.

- [ ] **Step 4: Conflict acceptance**

Provide two contradictory fixtures/sources; final result must surface unresolved disagreement rather than selecting a winner solely by count.

- [ ] **Step 5: Full suites**

```bash
python -m pytest -q
cd capt_ui/surfaces/desktop_swift
swift test
swift build --product CAPTNativeMac
```
