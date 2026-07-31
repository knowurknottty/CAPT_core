# CAPT Core

> AI work is easy to generate and hard to verify.

CAPT is a local-first verification substrate for AI systems. It binds claims, context, tool results, and actions to evidence, state, policy, and receipts so they can be inspected, reproduced, invalidated, and recovered across models and runtimes.

## Why CAPT Exists

AI systems produce claims that are easy to generate and hard to verify. Memory, tool use, workflow state, verification, governance, and authority are often attached after the fact as application-specific wrappers. This creates fragile systems whose continuity depends on one model, one vendor, one runtime, or one opaque session.

CAPT addresses the missing layer: persistent, inspectable cognitive infrastructure that remains stable while inference components change.

## What Problems CAPT Solves

- **Unverifiable claims** — CAPT records evidence with provenance, scope, confidence, and invalidation; claims without evidence stay marked as unproven.
- **State-bound verification** — Verified State Identity (VSI) binds verification results to concrete repository and runtime state. A passing test against an old state does not silently apply to a changed state.
- **Deterministic context exchange** — ContextPack v1 produces deterministic, digestible exchange artifacts with explicit assumptions and protected-fact validation.
- **Operation accountability** — Consequential local operations are recorded through append-only CTP receipts with idempotency and lifecycle tracking.
- **Governed optional behavior** — PULSE networking, ATE token extraction, and plugin capabilities degrade independently. An optional subsystem can fail without breaking the core.
- **Privacy-preserving defaults** — No required cloud account, external database, Docker runtime, or network activity in core imports.

## Quick Install

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
```

Or, from source:

```bash
python3 -m build
python3 -m venv /tmp/capt-test
/tmp/capt-test/bin/pip install dist/capt_solo-0.5.0-py3-none-any.whl
```

## Run Something

```bash
# Verify the runtime is healthy
capt --json doctor

# Run the self-test suite
python3 -m pytest -q

# Run the verification harness
python3 verify_runtime.py

# Run the five-minute walkthrough (local-only, no network)
python3 examples/verification_first/run.py --output /tmp/capt-verification-demo
```

The walkthrough creates a local subject, captures state-bound verification evidence, produces a CTP receipt and deterministic ContextPack, changes the subject, and demonstrates that the earlier verification no longer applies.

## What Happened

CAPT v0.5 is a bounded release of the verification kernel. It delivers:

| Deliverable | Status |
|---|---|
| Evidence engine with provenance and invalidation | Shipped |
| VSI state-bound verification | Shipped |
| Deterministic ContextPack v1 | Shipped |
| CTP append-only transaction journal | Shipped |
| ClaimGuard (scoped claim degradation) | Shipped |
| KHSB knowledge/coordination bus | Shipped |
| Plugin SDK + 46 registered tools | Shipped |
| Local-first security posture (no required network) | Shipped |
| Six-pillar public architecture (ADR-0008) | Documented |
| Repository governance (OWNER_DECISION_REGISTER) | Documented |
| Release audit harness (capt release validate) | Shipped |

### Deferred to v0.5.1 (ratified)

| Deferral | Reason |
|---|---|
| CAPT Spaces (multi-tenant isolation) | Architecture preserved; implementation deferred per OD-1 |
| Runtime adapters (MCP/A2A bindings) | Adapter seam defined; implementation deferred per OD-2 |
| RYS Bridge (remote runtime) | Private per RELEASE_GOVERNANCE D4 |

Full release decision record: `RELEASE_STATE.md`.

## Architecture Overview

CAPT's public architecture has six pillars:

```
Identity & Scope │ Evidence │ Verification │ Context │ Transactions │ Governance
```

Each pillar is a cross-cutting concept implemented by the runtime modules below.

```
┌──────────────────────────────────────────────────────────────────────┐
│ Adapters: CLI · CI · IDE · MCP · A2A · Hermes · model/tool providers │
└─────────────────────────┬────────────────────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────────────────────┐
│ Services: Memory · Workspace · Knowledge · Foundry · KHSB            │
│           Lifecycle · Procedures · domain engines                      │
└─────────────────────────┬────────────────────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────────────────────┐
│ CAPT Verification Kernel                                                │
│ Identity & Scope │ Evidence │ Verification │ Context │ Transactions  │
│ Governance                                                          │
└─────────────────────────┬────────────────────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────────────────────┐
│ Storage and Crypto Ports                                              │
│ record store · ledger · canonical codec · hashing · optional signing │
│ clock · policy store                                                    │
└──────────────────────────────────────────────────────────────────────┘
```

The constitutional layer model (L0–L11) assigns permanent ownership and dependency direction. `architecture/registry.yaml` inventories current, planned, external, and research subsystems. Neither the public pillars nor the internal ownership model are removed by a release.

### Public vs. Internal Architecture

The six pillars are the public mental model. The L0–L11 constitutional layer model assigns permanent ownership. `architecture/registry.yaml` is the machine-readable subsystem catalogue.

### Architecture Authority

| Document | Role |
|---|---|
| `CAPT_CANON.md` | Constitutional invariants (I-01..I-15). Highest authority. |
| `docs/CANONICAL_ARCHITECTURE.md` | Internal ownership map (L0–L11). Implementation converges toward this. |
| `docs/PUBLIC_ARCHITECTURE.md` | Public conceptual model (six pillars). ADR-0008. |
| `docs/adr/ADR-0008.md` | Decision record for the six-pillar architecture. |
| `architecture/registry.yaml` | Machine-readable subsystem registry with release targets. |

## Advanced Capabilities

### ClaimGuard

Scans claims for trigger verbs and degrades unsupported claims with scoped language. Never reports unverified as verified.

### Verified State Identity (VSI)

Binds verification results to concrete repository state (HEAD, file hashes, dependency state, runtime identity). Two VSIs are equivalent iff all fields match (except timestamp).

### ContextPack v1

Deterministic exchange artifact built from canonical JSON with digests, explicit assumptions, and protected-fact validation.

### Anti-Token Extraction (ATE)

Tool-output token extraction that preserves decision-relevant structure. Optional dependency; degrades gracefully when the external package is absent.

### CTP Transactions

Append-only transaction journal with idempotency, lifecycle state, receipts, and recovery.

## Developer Documentation

| Document | Description |
|---|---|
| `docs/CAPT_CANON.md` | Constitutional architecture (I-01..I-15 invariants) |
| `docs/CANONICAL_ARCHITECTURE.md` | Internal L0–L11 ownership map |
| `docs/PUBLIC_ARCHITECTURE.md` | Public six-pillar model |
| `docs/CAPABILITY_REGISTRY.md` | Capability catalogue |
| `docs/PUBLIC_API_STABILITY.md` | Stability tiers and compatibility declaration |
| `docs/RELEASE_GOVERNANCE.md` | Public/private release boundary |
| `docs/SECURITY_BOUNDARIES.md` | Trust boundaries |
| `docs/adr/` | Architecture Decision Records (ADR-0001..ADR-0012) |
| `docs/tutorials/VERIFY_AI_WORK_IN_FIVE_MINUTES.md` | End-to-end walkthrough |
| `docs/WHITEPAPER.md` | Design rationale and architecture |

## Governance

CAPT is governed by architectural invariants. Code changes must conform to the architecture; the architecture does not drift to match whatever code happens to exist. Every architectural decision is recorded as an ADR.

### Owner Decisions

All owner-gated release decisions are recorded in `docs/adr/ADR-0007.md` and `RELEASE_STATE.md`. Publication (push, tag, PyPI, deploy) is withheld until all gates pass and the owner authorizes it.

### Release State

- **Current status:** `HARDENING — NOT RELEASE READY`
- **Candidate SHA:** `UNFROZEN` (see `CURRENT_STATE.md`)
- **Publication:** `NOT PUBLISHED`
- **License:** MIT — see `LICENSE`

## Deep Architecture

For the complete internal architecture (L0–L11 layer definitions, subsystem registry, invariant specifications), see `CAPT_CANON.md` and `docs/CANONICAL_ARCHITECTURE.md`.

Each layer documents its responsibilities, public APIs, dependencies, persistence model, failure boundaries, and cross-layer communication protocols.

---

**CAPT is pre-release software. It has not been published to a package registry, tagged as v0.5.0, or approved for public release.** See `RELEASE_STATE.md` for the current gate status.
