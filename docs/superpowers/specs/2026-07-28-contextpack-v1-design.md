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

`schema_version` is the literal string `"capt.contextpack.v1"`.
`canonicalization_version` is `"capt-json-v1"`; `digest_algorithm` is
`"sha256"`. `evaluation_clock` is a visible, normalized ISO-8601 UTC field.
Serialization uses UTF-8, deterministic key and list ordering, compact
separators, explicit nulls, normalized timestamps, fixed JSON numeric values,
and never Python `repr()`. Intentional paths remain evidence; ambient local
paths do not enter a pack. The digest covers every semantic field below except
`digest` itself. Given identical source state, configuration, and evaluation
clock, construction returns identical canonical bytes and digest.

Required fields:

| Field | Source / meaning |
|---|---|
| `mission` | Stable mission id, current objective, and success criteria |
| `intent` | Purpose, priority, tradeoffs, success definition, safety constraints |
| `invariants` | Canonical inherited engineering constraints; supplied explicitly, never inferred from prose |
| `evidence` | Existing selected evidence records and their provenance |
| `memory` | Existing task-relevant retrieval/context-builder output only |
| `assumptions` | Explicit assumption, status, supporting evidence, missing evidence, required validation |
| `assumption_review_status` | `reviewed_none_found`, `reviewed_with_entries`, or `not_reviewed` |
| `protected_facts` | Source-derived paths, identifiers, versions, numbers, negations, errors, constraints, uncertainty, provenance |
| `protected_fact_review_status` | `reviewed` or `not_reviewed`; the latter blocks |
| `receipts` | Existing receipt references, not new signing authority |
| `rendered_context` | Model-neutral context produced from the existing builder |
| `token_budget` | Input budget, estimated use, remaining budget |
| `handoff` | Deterministic next-action resume artifact derived from pack contents |
| `confidence` | Explicit bounded confidence and unknowns; never silently promoted |
| `evaluation_clock` | Explicit input clock used for deterministic construction and validation |
| `digest` | Canonical pack digest |

Every referenced evidence, memory, assumption, receipt, invariant, and
protected fact has a stable `record_id`, `record_digest`, and `origin`. Portable
embedded material keeps those references alongside its embedded representation.
The builder preserves existing evidence status, uncertainty, contradictions,
confidence, provenance, and materially distinct duplicate claims; it only
canonicalizes order. It does not reconcile semantics.

`token_budget` distinguishes `maximum_input_tokens`, `reserved_output_tokens`,
`available_input_tokens`, `estimated_input_tokens`, `remaining_tokens`,
`tokenizer_id`, `estimation_method`, and `measurement_status`. The latter is
one of `measured`, `tokenizer_estimated`, `heuristic_estimated`, or `unknown`.
An exceeded declared budget blocks, while an estimate never masquerades as a
model-exact measurement.

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

AntiToken remains a validation boundary, not a summarizer. Protected facts are
first derived from source evidence, memories, constraints, and mission inputs;
the validator then compares those expected facts against `rendered_context`.
It reports facts as preserved, altered, or missing. It never defines source
truth from already-reduced output. A candidate pack is immutable; validation is
a separate immutable result that references its digest and never mutates it.

`ContextPackValidation` includes `pack_digest`, status, typed blocks, warnings,
missing and altered facts, token accounting, and remediation. Block categories
are `SCHEMA_BLOCK`, `INTEGRITY_BLOCK`, `FIDELITY_BLOCK`, `BUDGET_BLOCK`,
`PROVENANCE_BLOCK`, and `DETERMINISM_BLOCK`. Every block has a machine code,
explanation, affected fields, source references, remediation, and whether a
revised input may permit reconstruction. A blocked candidate is not a usable
ContextPack.

## API shape

The additive public surface is a dedicated `capt_solo.contextpack` package:

```python
build_context_pack(mission, intent, assumptions, *, evidence, memories,
                   receipts, invariants, token_budget, evaluation_clock) -> ContextPack
validate_context_pack(pack) -> ContextPackValidation
render_handoff(pack) -> Handoff
```

`MissionIntent`, `Assumption`, `ProtectedFact`, `ContextPack`,
`ContextPackValidation`, and `Handoff` are deeply immutable dataclasses:
tuples replace lists, nested values are immutable dataclasses or canonical
tuple pairs, and parsing defensively converts mutable input. They provide
`to_dict()` / `from_dict()` compatibility methods. `handoff` is derived from
the semantic pack fields, never accepted as caller-authored authoritative
prose; it contains mission/objective, established facts, unknowns, active
assumptions, blockers, failed attempts, next justified action, approvals, and
the pack digest. The CLI adds a separate
`context` group after the public API and tests exist. It does not alter existing
`memory`, `mission`, `evidence`, or `continuity` command semantics.

## Error semantics

- Invalid schema, timestamps, confidence, or digest: `BLOCK`.
- Missing intent, protected-fact review, or evaluation clock: `BLOCK`; no
  inferred default. The assumptions collection is required but may be empty;
  `reviewed_none_found` differs from `not_reviewed`, which blocks.
- Protected-fact loss: `BLOCK` with exact missing facts and source references.
- Empty retrieved memory is valid only when represented explicitly as empty;
  unknown evidence stays `unknown`, not successful retrieval.
- No method contacts a network, invokes a model, runs a drill, or persists a
  pack implicitly.

## Test contract

Tests must prove Phase I / Phase II continuity compatibility, existing context
builder adaptation, canonical ordering, repeatability with an explicit clock,
digest tamper detection, source-to-rendered protected-fact preservation,
explainable typed blocks, assumption visibility, handoff repeatability, token
accounting, no hidden writes, and no network access. Round trips must preserve
canonical bytes and digest: object → canonical dict → canonical JSON → parsed
object → canonical JSON. Strict v1 parsing rejects unknown semantic fields;
compatibility-inspection mode reports and preserves them without silently
recalculating a valid digest.

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
