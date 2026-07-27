# CAPT Character Genesis

Character Genesis is the first reusable entity compiler built on CAPT Meta Foundry.
It exists to create persistent, portable characters for children's video production
without reducing those characters to prompts or locking them to one renderer.

## Design objective

A character is treated as a persistent cognitive entity composed of:

- identity
- physical and visual form
- motion model
- voice model
- mind and emotional state
- relationships
- memory
- constitution
- continuity constraints
- explicit evolution events
- renderer adapters

The children's video workflow is the first consumer. The canonical package is also
intended to support books, comics, games, animation tools, voice systems, and future
CAPT embodiments.

## Trust boundary

Compilation does not imply rendering.

Character packages use the state `compiled_not_rendered`. Renderer execution remains
external. Visual validation remains `not_run` until actual media exists. Behavior tests
remain `specified_not_run` until a validator executes them.

## Creator authority

Every package enforces:

- creator control over canon
- human approval for canonical changes
- human approval before publication
- rejection of unapproved identity drift
- explicit child-safety rules
- no deceptive completion claims

## Canonical package

```text
character-package/
  identity.json
  physical.json
  visual.json
  motion.json
  voice.json
  mind.json
  emotion.json
  relationships.json
  memory.json
  constitution.json
  continuity.json
  evolution.json
  assets/
  behavior-tests/
  renderer-adapters/
  proof/
```

The current Python compiler emits the same structure as one deterministic artifact.
Filesystem package export remains a subsequent integration step.

## Continuity

Immutable traits are stored separately from versioned traits. Canon changes must be
represented as explicit, versioned evolution events. Rendered media may be rejected
when it conflicts with immutable traits or lacks approval evidence.

## Memory

Character memory is modeled as persistent episodic and semantic collections with a
canon-relevant-first retrieval policy. Durable CAPT Memory integration is intentionally
separate from the initial deterministic compiler so the object model can stabilize
before storage coupling.

## Renderer adapters

Renderer targets are declared as adapters rather than dependencies. An adapter may
export prompts, negative prompts, reference manifests, motion requirements, voice
requirements, and continuity checklists. The core package must remain usable when no
renderer is installed.

## Current maturity

Implemented:

- deterministic character package compilation
- typed genome structure
- continuity and drift policy
- bounded multidimensional emotions
- persistent memory contract
- child-safety constitution
- renderer-independent exports
- behavior-test declarations
- public API registration
- regression tests

Next gates:

- dedicated Character, Relationship, MemoryEvent, and EvolutionEvent dataclasses
- deterministic filesystem package export
- studio-to-character composition
- scene and shot continuity validators
- Seedance adapter package
- actual image/video validation hooks
- CTP receipts, KHSB events, durable Memory storage, and Proof Engine integration
