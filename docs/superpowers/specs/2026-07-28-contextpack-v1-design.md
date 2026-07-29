# ContextPack v1 — RC Contract Design

## Purpose

ContextPack v1 is CAPT Core's versioned, local-only exchange format for the
smallest sufficient engineering context. It is the RC ABI between Mission,
Memory/Retrieval, Evidence, AntiToken, model consumers, Hermes, and later
subsystems. It does not add a model integration, network transport, or new
persistence service.

## Boundaries

ContextPack v1 is additive. It adapts the existing context builder, Mission
checkpoint, evidence/receipt, and AntiToken contracts; it does not replace
them. Pack construction is read-only. Explicit export remains the caller's
responsibility. A pack is never silently written outside existing workspace
boundaries.

The RC excludes persistent investigation journals, decision persistence,
quality scoring, context-diff history, adaptive attention, scheduling, HMC
paging, strategy engines, multi-tier memory, self-reflection, and knowledge
distillation.

## Canonical contract

`schema_version` is the literal string `"context-pack/v1"`. Serialization uses
canonical JSON: UTF-8, stable key ordering, compact separators, and a SHA-256
digest over the pack excluding its `digest` field. Given identical source
state, configuration, and evaluation clock, construction returns byte-stable
logical content and the same digest.

Required fields:

| Field | Source / meaning |
|---|---|
| `mission` | Stable mission id, current objective, and success criteria |
| `intent` | Purpose, priority, tradeoffs, success definition, safety constraints |
| `invariants` | Canonical inherited engineering constraints; supplied explicitly, never inferred from prose |
| `evidence` | Existing selected evidence records and their provenance |
| `memory` | Existing task-relevant retrieval/context-builder output only |
| `assumptions` | Explicit assumption, status, supporting evidence, missing evidence, required validation |
| `protected_facts` | Paths, identifiers, versions, numbers, negations, errors, constraints, uncertainty, provenance |
| `receipts` | Existing receipt references, not new signing authority |
| `rendered_context` | Model-neutral context produced from the existing builder |
| `token_budget` | Input budget, estimated use, remaining budget |
| `handoff` | Deterministic next-action resume artifact derived from pack contents |
| `confidence` | Explicit bounded confidence and unknowns; never silently promoted |
| `digest` | Canonical pack digest |

## Construction flow

```text
Mission + Intent + constraints
        + selected Evidence + task-relevant Retrieval
        + explicit Assumptions + receipts
                    |
          existing Context Builder
                    |
     Protected-fact extraction / AntiToken validation
                    |
     PASS -> ContextPack v1 + deterministic handoff
     BLOCK -> explain protected-fact loss; emit no usable pack
```

AntiToken remains a validation boundary, not a summarizer. If its existing
fidelity checks or ContextPack protected-fact checks show loss, generation
returns an explainable `BLOCK` with missing facts and remediation. It must not
silently truncate or replace facts.

## API shape

The additive public surface is a dedicated `capt_solo.contextpack` package:

```python
build_context_pack(mission, intent, assumptions, *, evidence, memories,
                   receipts, invariants, token_budget, evaluation_clock) -> ContextPack
validate_context_pack(pack) -> ContextPackValidation
render_handoff(pack) -> Handoff
```

`MissionIntent`, `Assumption`, `ProtectedFact`, `ContextPack`,
`ContextPackValidation`, and `Handoff` are immutable dataclasses with
`to_dict()` / `from_dict()` compatibility methods. The CLI adds a separate
`context` group after the public API and tests exist. It does not alter existing
`memory`, `mission`, `evidence`, or `continuity` command semantics.

## Error semantics

- Invalid schema, timestamps, confidence, or digest: `BLOCK`.
- Missing intent, assumptions field, protected facts, or evaluation clock:
  `BLOCK`; no inferred default.
- Protected-fact loss: `BLOCK` with exact missing facts and source references.
- Empty retrieved memory is valid only when represented explicitly as empty;
  unknown evidence stays `unknown`, not successful retrieval.
- No method contacts a network, invokes a model, runs a drill, or persists a
  pack implicitly.

## Test contract

Tests must prove Phase I / Phase II continuity compatibility, existing context
builder adaptation, canonical ordering, repeatability with an explicit clock,
digest tamper detection, protected-fact preservation, explainable blocks,
assumption visibility, handoff repeatability, token accounting, no hidden
writes, and no network access.

## Deferred interface contracts

The following are architecture-only post-RC modules. They may consume or
produce ContextPack v1-compatible data, but no runtime implementation ships in
RC-1:

- Investigation Journal: observation/hypothesis/experiment/result/conclusion.
- Decision Intelligence: searchable decision and alternative records.
- Context Quality Metrics and Context Diff: analysis over completed packs.
- Cognitive Scheduler and Attention Engine: future selection policies.
- Hierarchical Memory and HMC Integration: future memory providers.
- Strategy Layer and Cognitive Garbage Collection: future governance policies.

Any future version must preserve v1 parsing or publish an explicit migration;
it may not redefine v1 receipts, provenance, or local-first boundaries.
