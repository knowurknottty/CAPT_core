# Search + Deep Research Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add distinct Search and Deep Research execution modes with explicit governed wall-clock/retrieval budgets so long-form work can complete without globally weakening CAPT's interactive timeout discipline.

**Architecture:** Immutable workload profiles are resolved before RuntimeService admission and bound into approval. Search is a bounded retrieval plan. Deep Research is a multi-stage plan (`decompose -> retrieve -> claim_map -> adversarial_check -> synthesize`) with source/claim provenance. Token context and wall-clock ceilings remain separate dimensions.

**Tech Stack:** Python CAPT RuntimeService/EventStore/provider driver/ContextPack; existing approval binding; configured retrieval adapters; Swift composer/result presentation; pytest/Swift tests.

**Spec:** Parent design Part IV §§26-29 plus composer parity contract Search/Deep Research sections.

## Global Constraints

- Ordinary interactive chat remains at a 120-second ceiling in this release.
- Profile ID and resolved budget are approval-bound and immutable after approval.
- Context-token capacity never implies sufficient wall-clock budget.
- Research output remains evidence/analysis until verification.
- Source count/majority is not truth.
- Every retrieved source records URL, retrieval timestamp, content digest, and adapter/provider.
- Search and Deep Research are distinct modes.
- Research network capability never grants network access to quarantine scanners or unrelated execution surfaces.

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
- current provider-driver timeout call site.
- `CAPTChatCoordinator.swift`
- `CAPTOperatorStore.swift`
- `CAPTComposerContext.swift`

---

### Task 1: Workload profile contract

**Interfaces:** Produces `WorkloadProfile`, `resolve_workload_profile(profile_id) -> WorkloadProfile`.

- [ ] **Step 1: Write RED profile tests**

```python
from capt_runtime.workload_budget import resolve_workload_profile


def test_interactive_profile_remains_bounded():
    p = resolve_workload_profile("interactive_chat")
    assert p.wall_seconds == 120
    assert p.max_retrieval_rounds == 0


def test_deep_research_has_larger_explicit_budget():
    p = resolve_workload_profile("deep_research")
    assert p.wall_seconds == 600
    assert p.max_retrieval_rounds == 8
```

- [ ] **Step 2: Implement immutable profiles**

```python
from dataclasses import dataclass

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

def resolve_workload_profile(profile_id: str) -> WorkloadProfile:
    try:
        return PROFILES[profile_id]
    except KeyError as exc:
        raise ValueError("UNKNOWN_WORKLOAD_PROFILE:" + profile_id) from exc
```

- [ ] **Step 3: Add invalid-profile rejection test**

Unknown explicit ID raises `UNKNOWN_WORKLOAD_PROFILE` before dispatch; there is no fallback.

- [ ] **Step 4: Commit**

```bash
git add capt_runtime/workload_budget.py tests/capt_runtime/test_workload_budget.py
git commit -m "feat(runtime): add governed workload budgets"
```

---

### Task 2: Bind workload profile to approval/provenance

**Interfaces:** Approval binding gains `workloadProfileId` plus resolved budget fields; provenance gains ceilings, not claimed usage.

- [ ] **Step 1: Write RED mutation test**

Approve `interactive_chat`; execute as `deep_research` with same approval ID -> `MODEL_PROMPT_APPROVAL_WORKLOAD_MISMATCH`, zero DriverRuns/external dispatch.

- [ ] **Step 2: Extend deterministic binding**

`workloadProfileId`, `effectiveWallClockSeconds`, `maxRetrievalRounds`, and `maxSources` enter the bound execution data/prepared digest. Resolve once during preparation and freeze.

- [ ] **Step 3: Extend cognitive provenance**

```json
{
  "workloadProfileId": "deep_research",
  "effectiveWallClockSeconds": 600,
  "maxRetrievalRounds": 8,
  "maxSources": 64
}
```

- [ ] **Step 4: Commit**

```bash
git add capt_runtime/model_approval_binding.py capt_runtime/operator_provenance.py desktop tests
git commit -m "feat(runtime): bind workload profile to model approval"
```

---

### Task 3: Provider timeout consumes the admitted profile

**Interfaces:** Provider execution receives `timeout_seconds` from immutable prepared execution.

- [ ] **Step 1: Write RED propagation test**

Fake transport records timeout: `interactive_chat == 120`, `code_review_deep == 300`, `deep_research == 600`.

- [ ] **Step 2: Thread frozen timeout to provider call**

No UI/provider preference reread after admission. Remove the hidden hard-coded 120 seconds only at the provider call site; interactive profile preserves 120 behavior.

- [ ] **Step 3: Preserve typed timeout failure**

Provider timeout remains `PROVIDERDRIVERFAILURE` with timeout detail; existing DriverRun/task recovery semantics remain unchanged.

- [ ] **Step 4: Re-run known long-context case**

Same ~10K-token CAPT Swift review dossier: `interactive_chat` ceiling remains 120; `code_review_deep` admits 300. Record actual elapsed duration and provider outcome independently of ceiling.

- [ ] **Step 5: Commit**

```bash
git add capt_runtime desktop tests
git commit -m "fix(runtime): enforce admitted provider wall-clock budget"
```

---

### Task 4: Typed Search/Deep Research plan model

**Interfaces:** Produces exact `ResearchStage`, `ResearchPlan`, `ResearchSourceRecord`, `ResearchClaimRecord`.

- [ ] **Step 1: Write RED plan tests**

```python
from capt_runtime.research import ResearchPlan


def test_search_plan_is_bounded():
    p = ResearchPlan.for_mode("search", "current GPU rental pricing", max_sources=12)
    assert [s.kind for s in p.stages] == ["retrieve", "source_check", "synthesize"]
    assert p.max_sources == 12


def test_deep_research_has_adversarial_stage():
    p = ResearchPlan.for_mode("deep_research", "question", max_sources=64)
    assert [s.kind for s in p.stages] == [
        "decompose", "retrieve", "claim_map", "adversarial_check", "synthesize"
    ]
```

- [ ] **Step 2: Implement exact dataclasses/templates**

```python
from dataclasses import dataclass
from hashlib import sha256

@dataclass(frozen=True)
class ResearchStage:
    stage_id: str
    kind: str
    purpose: str
    input_refs: tuple[str, ...]
    max_sources: int
    max_retrieval_rounds: int

@dataclass(frozen=True)
class ResearchSourceRecord:
    source_id: str
    url: str
    retrieved_at: str
    content_digest: str
    provider: str
    title: str

@dataclass(frozen=True)
class ResearchClaimRecord:
    claim_id: str
    statement: str
    supporting_source_ids: tuple[str, ...]
    contradicting_source_ids: tuple[str, ...]
    status: str

@dataclass(frozen=True)
class ResearchPlan:
    plan_id: str
    mode: str
    objective: str
    stages: tuple[ResearchStage, ...]
    max_sources: int

    @staticmethod
    def for_mode(mode: str, objective: str, *, max_sources: int) -> "ResearchPlan":
        templates = {
            "search": (
                ("retrieve", "Discover bounded relevant sources", 2),
                ("source_check", "Check source identity, recency, and conflicts", 0),
                ("synthesize", "Synthesize sourced answer without inventing verification", 0),
            ),
            "deep_research": (
                ("decompose", "Decompose the research question", 0),
                ("retrieve", "Retrieve bounded source set", 8),
                ("claim_map", "Map claims to supporting and contradicting sources", 0),
                ("adversarial_check", "Challenge high-impact claims and unresolved gaps", 4),
                ("synthesize", "Synthesize converged, dissenting, and unresolved findings", 0),
            ),
        }
        if mode not in templates:
            raise ValueError("UNKNOWN_RESEARCH_MODE:" + mode)
        seed = (mode + "\x00" + objective).encode("utf-8")
        plan_id = "research-" + sha256(seed).hexdigest()[:24]
        stages = tuple(
            ResearchStage(
                stage_id=f"{plan_id}-stage-{index + 1}",
                kind=kind,
                purpose=purpose,
                input_refs=(),
                max_sources=max_sources if kind in {"retrieve", "adversarial_check"} else 0,
                max_retrieval_rounds=rounds,
            )
            for index, (kind, purpose, rounds) in enumerate(templates[mode])
        )
        return ResearchPlan(plan_id, mode, objective, stages, max_sources)
```

`ResearchClaimRecord.status` is validated by constructor/helper to one of `supported`, `contradicted`, `mixed`, `insufficient`, `unresolved`.

- [ ] **Step 3: Add invalid mode/status tests**

Any mode besides `search`/`deep_research` rejects. Normal chat creates no ResearchPlan. Invalid claim status rejects.

- [ ] **Step 4: Commit**

```bash
git add capt_runtime/research.py tests/capt_runtime/test_research_plan.py
git commit -m "feat(research): add governed search and deep research plans"
```

---

### Task 5: Retrieval/source registry and claim graph

**Interfaces:** `register_source(...) -> ResearchSourceRecord`; `build_claim_record(...) -> ResearchClaimRecord`.

- [ ] **Step 1: Write RED provenance/conflict tests**

Same URL with different retrieval timestamp/digest -> distinct source IDs. Contradictory source remains attached to claim; never deleted because it is minority evidence.

- [ ] **Step 2: Implement canonical source identity**

Canonical URL + retrieval timestamp + content digest determine source ID. Store adapter/provider/title. Bounded excerpts are presentation/policy data, not identity.

- [ ] **Step 3: Implement claim status rules**

Supporting only -> `supported`; contradicting only -> `contradicted`; both -> `mixed`; no adequate evidence -> `insufficient`; unresolved adversarial conflict -> `unresolved`.

- [ ] **Step 4: Implement adversarial-check requirements**

For every high-impact claim record, stage records at least one performed check type: `contradictory_source_search`, `source_authority_challenge`, `temporal_staleness_check`, or `missing_evidence_check`. Inability to resolve remains `unresolved`.

- [ ] **Step 5: Commit**

```bash
git add capt_runtime/research.py tests/capt_runtime/test_research_plan.py
git commit -m "feat(research): preserve source and claim provenance"
```

---

### Task 6: Swift research mode/progress models

**Interfaces:** `CAPTExecutionMode.workloadProfileID`; `CAPTResearchStageSnapshot`.

- [ ] **Step 1: Write RED mappings**

```swift
#expect(CAPTExecutionMode.normal.workloadProfileID == "interactive_chat")
#expect(CAPTExecutionMode.search.workloadProfileID == "search")
#expect(CAPTExecutionMode.deepResearch.workloadProfileID == "deep_research")
```

`code_review_deep` is selected only by the explicit governed code-review action/profile, not ordinary composer Normal mode.

- [ ] **Step 2: Implement stage snapshot**

```swift
public struct CAPTResearchStageSnapshot: Codable, Equatable, Sendable, Identifiable {
    public let id: String
    public let kind: String
    public let state: String
    public let sourceCount: Int
}
```

- [ ] **Step 3: Render human progress**

Map stages to public labels: `Searching sources`, `Checking sources`, `Mapping claims`, `Challenging claims`, `Synthesizing`. Raw stage envelopes remain in Raw details.

- [ ] **Step 4: Commit**

```bash
git add capt_ui/surfaces/desktop_swift
git commit -m "feat(mac): bind research modes to governed workload profiles"
```

---

### Task 7: Search + Deep Research acceptance

- [ ] Profile mutation after approval -> rejection/zero dispatch.
- [ ] Ordinary chat ceiling = 120; deep code review = 300; Deep Research = 600; actual durations recorded separately.
- [ ] Search source record contains URL/retrieval timestamp/digest/provider.
- [ ] Contradictory controlled sources produce `mixed`/`unresolved`, never winner-by-count.
- [ ] Research synthesis remains unverified evidence until VerificationPipeline action.
- [ ] Run full Python suite, Swift tests, and `swift build --product CAPTNativeMac` with zero failures.
