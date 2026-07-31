# ADR-0001 — Canonical CAPT Agent Runner ownership

Status: ACCEPTED (owner-approved 2026-07-31)
Deciders: Owner (Captain), HY3
Supersedes: milestone language "GOVERNED_AGENT_BOOT_PROVEN" as previously
asserted for the Hermes outer loop (corrected to
GOVERNED_EXTERNAL_TURN_TRANSACTION_PROVEN).

## Context

Phase 0 proved the outer Hermes/HY3 loop is transcript-authoritative and exposes
no blocking pre-first-call control seam (OUTER_AGENT_BOOT_TRACE.md,
OUTER_AGENT_MEMORY_GAP_REPORT.md). Nested ModelTask governance passing does not
imply outer-agent CAPT continuity.

## Decision

The canonical outer-loop composition and control boundary is a standalone CAPT
Agent Runner (`capt_solo/agent/`), composing the existing proven CAPTRuntime +
ModelProvider path. CAPT owns the complete outer loop. Rejected: Outcome A
(Hermes hook-as-gate) and Outcome B (Hermes-wrapping launcher, canonical). B may
survive only as a future transitional compatibility launcher. See
OUTER_AGENT_MEMORY_DECISION.md, OPTION_B/C analyses.

## Consequences

- New `capt agent` CLI group; new `capt_solo/agent/` package composing api.py
  surface only; no parallel composition root; no Hermes clone.
- Runtime-enforced invariants: no model call before MemoryUseGate PASS; request
  rendered from CAPT state; fresh-process resume from CAPT; native compaction
  never the continuity mechanism.
- Runtime-owned OutputPolicy (CaveCAPT default) — provider cannot decide
  verbosity; safety/blocker/gate-failure messages bypass caps.
- Hermes plugin retained as observational compatibility/migration only; its docs
  corrected to state it does NOT establish authoritative CAPT boot/continuity.
- Milestones GOVERNED_AGENT_BOOT_PROVEN + GOVERNED_AGENT_CONTINUITY_PROVEN
  claimable only after acceptance gates pass with evidence;
  GOVERNED_TOOL_LOOP_PROVEN out of scope for V1.

## Compliance

- Composition-root uniqueness enforced by test (no-duplicate-composition-root).
- ClaimGuard governs all completion language; no hardcoded verdicts.
- Evidence persisted per acceptance gate; reconstructable from CAPT state.
