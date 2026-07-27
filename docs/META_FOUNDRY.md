# CAPT Meta Foundry

CAPT Meta Foundry is a local-first, proof-governed substrate for creating domain-specific creation systems. It converts creator intent into versioned specifications, deterministic compiler outputs, typed constraints, provenance records, and portable artifact packages.

It is not a media model and does not claim that exported prompts are rendered assets.

## Trust boundary

Meta Foundry distinguishes four states:

1. **Specified** — creator intent has been normalized into a versioned domain specification.
2. **Compiled** — a registered compiler has produced a structured artifact.
3. **Rendered** — an external or local renderer has produced media or another terminal artifact.
4. **Validated** — declared validators have inspected the rendered artifact and recorded evidence.

These states are not interchangeable. A compiled Seedance prompt package is not a rendered video, and a rendered video is not continuity-valid until validation actually runs.

## Initial public vertical slice

The `capt_solo.meta_foundry` package currently provides:

- domain and compiler registries;
- creation intents and normalized specifications;
- deterministic compiler execution;
- typed constraint evaluation;
- explicit compiler lifecycle enforcement;
- field-level provenance records;
- canonical JSON hashing and export;
- a renderer-independent Children's Studio reference domain.

The initial implementation is in-memory and dependency-free. Persistence through CAPT Memory, CTP transaction receipts, KHSB events, Knowledge Bubble packaging, and Proof Engine integration are the next integration gates; they are not claimed as complete in this slice.

## Compiler lifecycle

Compiler definitions use the following states:

```text
candidate -> generated -> quarantined -> validated -> approved -> registered
                                                               -> revoked
```

Only `registered` compilers may execute. Generated compiler candidates must not be imported or executed directly.

## Determinism contract

A deterministic compiler must produce the same payload and content hash from the same specification content, compiler ID, and compiler version. Artifact instance IDs and timestamps may differ; they are excluded from the content hash.

Changing the compiler version intentionally changes artifact identity.

## Domain architecture

A domain declares:

- stable domain identifier;
- semantic version;
- available compiler IDs;
- output constraints;
- domain description and trust expectations.

A domain compiler accepts a `DomainSpecification` and returns a JSON-compatible mapping. The Meta Foundry wraps that payload with source identifiers, provenance, validation state, compiler identity, and a deterministic content hash.

## Constraint operators

The first implementation supports:

- `exists`
- `equals`
- `not_equals`
- `in`
- `not_in`
- `range`

Constraints use JSON-style paths beginning with `$.` and carry `info`, `warning`, or `error` severity. Failed `error` constraints prevent artifact creation.

## Children's Studio reference domain

Identifier:

```text
org.inversionlabs.childrens-studio
```

Compiler:

```text
childrens-studio.package
```

The compiler emits a canonical studio package containing:

- creative objective and audience;
- studio constitution;
- empty but typed canon registries;
- production stages;
- renderer selection metadata;
- renderer package requirements;
- assumptions and unresolved questions;
- explicit `compiled_not_rendered` state;
- explicit `visual_validation: not_run` state.

The reference domain is intentionally renderer-independent. Seedance, Veo, Sora, Kling, local video models, voice systems, and publishing services belong behind optional adapters.

## Public API example

```python
from capt_solo.api import DomainRegistry, MetaFoundry, register_childrens_studio
from capt_solo.meta_foundry.childrens_studio import COMPILER_ID, DOMAIN_ID

registry = DomainRegistry()
register_childrens_studio(registry)
foundry = MetaFoundry(registry)

intent = foundry.create_intent(
    domain_id=DOMAIN_ID,
    objective="Create a nature-adventure cartoon channel for ages 5-8",
    audience={"age_min": 5, "age_max": 8},
    constraints={"episode_minutes": 6, "violence": "none"},
    preferences={"renderer": "seedance", "aspect_ratio": "16:9"},
)

specification = foundry.specify(
    intent.intent_id,
    assumptions=("Initial release language is English.",),
    unresolved_questions=("Final channel name is not selected.",),
)

artifact = foundry.compile(specification.specification_id, COMPILER_ID)
print(foundry.export_artifact(artifact))
```

## Required next gates

Before Meta Foundry is represented as fully integrated with CAPT v0.4, the branch must add and verify:

1. durable Memory Engine persistence for intents, specifications, compiler records, artifacts, and provenance;
2. CTP-bounded compilation with commit/abort receipts and idempotency keys;
3. KHSB lifecycle events without coupling domain compilers to the bus;
4. Proof Engine evidence and ClaimGuard verdicts for compiler and workflow claims;
5. quarantine-by-default domain package import through Knowledge Bubbles;
6. declarative compiler manifests with static validation;
7. renderer export adapters, beginning with a local filesystem package;
8. character, world, episode, scene, shot, and continuity compilers;
9. visual-validation adapter contracts that report `not_run` when unavailable;
10. migration, tamper, recovery, and deterministic replay tests.

## Non-goals for the first public release

- Direct vendor API execution by default.
- Autonomous YouTube publishing.
- Unreviewed self-modifying Python compilers.
- Voice cloning.
- Automated revenue manipulation.
- Claiming visual continuity from prompts alone.
- Treating model-generated suggestions as creator-approved canon.
