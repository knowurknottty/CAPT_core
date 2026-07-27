# WORKSPACE.md — CAPT Universal Workspace Specification

CAPT is **workspace-native, not prompt-native**. This document defines the
persistent, structured execution context that lives in the repository so that a
capable agent can enter the repo and continue work safely — without relying on
provider-specific system prompts, proprietary project containers, or hidden
conversational memory.

## Purpose

A model should not require a giant bootstrap prompt to understand the repository.
A new agent should be able to: open the repo → read one entrypoint → discover
governing authority → determine current state → locate the active task → verify
prior evidence → resume from the last checkpoint → operate within explicit
permissions and stop conditions.

## Workspace contents

The workspace is a persistent execution context containing:

| Class | What it holds | Where |
|-------|---------------|-------|
| Identity | Agent/self boundary, scoping | `docs/CAPT_CANON.md` §3, L0 |
| Constitution | Invariants I-01..I-15 | `docs/CAPT_CANON.md` §2 |
| Architecture | Layers, canonical homes, registry | `docs/CANONICAL_ARCHITECTURE.md`, `architecture/registry.yaml` |
| Current state | Branch, HEAD, cleanliness, release target, test results | `CURRENT_STATE.md` |
| Task state | Queue + machine-readable records | `TASK_QUEUE.md`, `tasks/` |
| Checkpoints | Resume contracts (historical archived) | `CHECKPOINT.md`, `checkpoints/` |
| Evidence | Test reports, audits, benchmarks | `docs/evidence/`, `evidence/`, `checkpoints/` |
| Decisions | ADRs and recorded exceptions | `docs/adr/`, `decisions/` |
| Tools | CLI, scripts, harness adapters | `capt_cli.py`, `tools/`, `TOOLING.md` |
| Capabilities | Declared agent/harness abilities | `architecture/agent-capabilities.schema.json`, `capt workspace capabilities` |
| Memory | Durable observations (agent-local) | `memory/` |
| Knowledge | Curated, approved retained context | `knowledge/` |
| Release state | Readiness, gates, blockers | `RELEASE_STATE.md` |
| Security boundaries | Trust boundaries, untrusted-content handling | `SECURITY_BOUNDARIES.md` |
| Logs | Structured run logs (ephemeral-safe) | `logs/` |

## State classes (do not confuse them)

- **Canonical truth** — approved definitions, architecture, invariants, ADRs.
  Changed only via ADR. Source: `docs/CAPT_CANON.md`, `architecture/registry.yaml`, `docs/adr/`.
- **Implementation state** — what the code actually does now. Evidence, not authority.
- **Task state** — what is being worked on; `TASK_QUEUE.md` + `tasks/`.
- **Agent-local scratch state** — a single agent's in-flight reasoning; never
  promoted to canonical without review.
- **Durable memory** — approved retained observations in `memory/`.
- **Evidence** — test reports, benchmarks, audits in `docs/evidence/`, `evidence/`.
- **Inference** — derived conclusions; must cite evidence; `unknown` is allowed.
- **Unresolved contradiction** — a surfaced conflict between the above; tracked,
  not silently fixed.

## What an autonomous agent may modify

Allowed without explicit approval (per `AGENTS.md`):

- Task records it owns (`tasks/*.json` status transitions, with commit reference).
- `CURRENT_STATE.md` / `CHECKPOINT.md` live sections (machine-derived portions).
- `evidence/`, `logs/`, `memory/` (durable observations only).
- Refactors, deduplication, tests, docs, validation, packaging that preserve
  public behavior and invariants.

## What requires explicit approval (owner gates)

- Public/private boundary ([B]).
- Licensing changes.
- Security disclosures.
- Destructive migrations.
- Irreconcilable canonical conflicts.
- Anything needing external credentials or publish/push rights.

## Resume protocol

1. `AGENTS.md` → authority order + startup procedure.
2. `CURRENT_STATE.md` → where we are.
3. `CHECKPOINT.md` → exact next command + active files.
4. `TASK_QUEUE.md` / `tasks/` → what to do next (`capt workspace next`).
5. `capt workspace validate` → confirm workspace is internally consistent.
6. Do the work; update task status; on stop, write a checkpoint.

## Concurrency

Multiple agents may work from the same workspace. Safety rules:

- Tasks have stable IDs; checkpoints identify branch + commit.
- A stale checkpoint (commit no longer HEAD) is detectable and must be flagged.
- Concurrent task claims are detectable via `status` + `assigned_agent`.
- An agent must not overwrite another agent's active task silently.
- Task completion must reference a commit SHA.
- Merge conflicts remain visible; no silent resolution.

No distributed coordinator is implemented. Deterministic file + Git semantics are
the concurrency model.
