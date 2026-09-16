# CAPT Core Design Rationale

CAPT treats a model as a replaceable inference component inside a larger governed system. The model can reason and generate; CAPT owns the durable responsibilities that should survive model/provider/session changes.

## Design thesis

Most AI systems leave too much responsibility inside a bounded probabilistic context window: memory, execution history, tool authority, self-checking, recovery, and completion judgments.

CAPT externalizes those responsibilities into inspectable system components.

## Core principles

### Durable state belongs outside inference

Persistent memory, mission/task state, evidence, checkpoints, and runtime history must survive model replacement.

### Authority is explicit

A model response is not an authorization. Capabilities, leases, approvals, policies, and RuntimeService transitions define what work may occur.

### Evidence is not self-verification

CAPT separates observation, evidence admission, verification, claim support, and completion. A fluent model cannot collapse those boundaries by assertion.

### Recovery must prefer truth over convenience

Idempotency and checkpointing reduce repeated work, but external side effects can become indeterminate. When CAPT cannot prove whether dispatch occurred, the correct design is suspension/reconciliation—not optimistic redispatch.

### Operator surfaces remain thin

CLI, TUI, and desktop clients provide control and visibility without duplicating runtime authority. The merged semantic operator-control API coordinates revisioned configuration and session/proposal cursors; EventStore remains the authority for execution and completion. Read projections report that state without granting authority.

### Prompt intelligence remains subordinate to governance

The merged prompt-proposal/intelligence layer may improve and explain a request, but it may not mint capability, bypass human review, fabricate evidence, or redefine mission state.

### Multi-perspective cognition does not imply multi-runtime authority

Cohorts may coordinate competing perspectives, quorum, and dissent while RuntimeService/EventStore remain authoritative. The merged Model Council alpha adds logical topology, launch contracts, and deterministic claim analysis; UPG-024 separately adds cognitive-debt projection. None of those source surfaces establishes live model quality, achieved provider concurrency, or full product-plan completion.

### Local-first is a deployment property, not a security proof

Keeping core state local reduces mandatory cloud dependence. It does not automatically provide encryption at rest, multi-user isolation, signed audit roots, or protection from a compromised host.

## Why CAPT uses multiple evidence classes

A source file, unit test, controlled HTTP protocol test, exact-head integration test, installed-wheel run, live-provider run, and process-boundary restart test prove different things. CAPT documents the smallest claim supported by the strongest matching evidence.

## What CAPT is not

CAPT is not a model, not a prompt wrapper, not Hermes, not a UI-only agent shell, not an operating-system security boundary, and not a claim that every research seam is production-ready.

See [`ARCHITECTURE.md`](ARCHITECTURE.md), [`CURRENT_STATE.md`](CURRENT_STATE.md), and [`SECURITY.md`](SECURITY.md).
