# CAPT Bot Foundation R1

## Thesis

CAPT Bot is a persistent governed synthetic worker. It separates identity, cognition, authority, runtime locality, collaboration, and verification so a friendly Bot surface never becomes the security boundary.

## Non-negotiable invariants

1. Identity is not authority. Cloning a Bot must not clone credentials or capabilities.
2. Authority is absent until explicitly constructed by CAPT governance.
3. Trust may reduce approval friction, but never removes provenance, receipts, or verification.
4. Persistent cognition is typed and provenance-bound; Markdown is a projection, not canonical state.
5. Learned state is proposed, validated, promoted, monitored, and revocable; no model may grant itself persistence authority.
6. Runtime locality belongs to each operation/data class, not permanently to the Bot identity.
7. Crew members are persistent identities; delegates are bounded mission-scoped workers; councils are temporary deliberation structures.
8. Human-only blockers are enforced as state-machine authority, not UI convention.
9. Skills are governed learned software with lifecycle, evidence, and rollback semantics.
10. EventStore remains the authoritative mutation path; no parallel Bot database may become a second truth source.

## R1 scope

R1 adds authoritative contracts and state machines for Bot manifests, cognitive promotion candidates, Skill Workshop candidates, and Lab Board items. It also adds the first locality-policy compiler used by onboarding and preserves the existing capability, approval, memory, Cohort, ToolBroker, WORLD RECEIPT, and verification planes.
## Bot manifest

A Bot manifest composes six independently governed concerns: identity, cognitive policy, model strategy, authority template, runtime locality, and collaboration role. R1 stores references and policy declarations only; API keys and live capability leases remain in their existing authority stores.

The manifest distinguishes `crew` from `delegate`. Crew identities are durable and may accumulate governed cognition. R1 delegates must resolve to an existing durable mission; explicit task/call binding and expiry are deferred rather than implied. Model choice is a strategy field and never part of identity.

## Locality policy

The R1 onboarding compiler accepts locality/privacy intent: whether cloud execution is allowed, whether private data may enter cloud execution, and an optional preferred runtime. It emits a deterministic policy with safe defaults. `local_only` data cannot be assigned to cloud execution. Cloud eligibility does not itself grant network, filesystem, credential, or tool authority; mutation, delegation, and cost policy compilation remain later layers.

## Governed cognition

Cognitive candidates classify proposed persistence as observation, user fact, derived fact, preference, decision, hypothesis, belief, contradiction, open question, procedure, skill, or relationship. Every candidate carries source references, provenance, sensitivity, confidence, and promotion mode, but RuntimeService requires its Bot to exist and requires that promotion mode to match the Bot's durable cognition policy.

Promotion modes are `locked`, `governed`, and `autonomous`. Locked requires a human decision. Governed may be promoted by the governance kernel when policy permits. Autonomous still requires a governance decision record; it never means self-authorized model persistence.

## Skill Workshop

Skill candidates belong to an existing durable Bot and move through `idea -> draft -> review -> sandbox -> test -> red_team -> shadow -> approved -> active`. They may also become `rejected`, `revoked`, or `superseded`. Final approval/revocation requires human or governance authority; once authority has sealed a final state, cognition cannot unwind that decision.
## Lab Board

Lab Board items are EventStore-backed projections of work and human dependency. Mission binding is optional, but any supplied `missionId` must resolve to durable Mission state. R1 states are `inbox`, `ready`, `active`, `verifying`, `waiting_agent`, `waiting_human`, `human_task`, `blocked_human`, and `done`.

A `blocked_human` item may be enriched by agents with evidence and requested action, but only a human actor may transition it out of that state. This is enforced inside the aggregate transition function.

## Persistence and events

R1 introduces closed contract events rather than arbitrary extension payloads: `BotRegistered`, `CognitiveCandidateProposed`, `CognitiveCandidateDecided`, `SkillCandidateCreated`, `SkillCandidateTransitioned`, `LabBoardItemCreated`, and `LabBoardItemTransitioned`.

Each stream has exclusive aggregate field ownership and is committed through RuntimeService/EventStore with normal idempotency, hash chaining, encrypted-at-rest state, and outbox semantics.

## Explicit non-goals for R1

R1 does not ship Cloudflare adapters, browser execution, Bot UI, standup UI, Markdown projection, demonstration-to-skill automation, knowledge-graph consolidation, or cross-node agent scheduling. Those are downstream consumers of the authority model established here.