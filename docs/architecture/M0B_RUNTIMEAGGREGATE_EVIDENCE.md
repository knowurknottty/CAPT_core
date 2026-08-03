# M0-B RuntimeAggregate Evidence Collection (Part 16)

Status: NOT IMPLEMENTED (per mission Part 16 — collect evidence only, do not
implement RuntimeAggregate during M0-B). This document records what the M0-B
read-only driver proof revealed about a future RuntimeAggregate, and recommends
whether to implement it now, revise the proposal, or defer further.

## What the M0-B proof exposed about runtime-wide state

1. **Runtime identity needs.** The driver proof required a stable `runtimeId`
   only to namespace the driver registry and the target-repo staging root. The
   registry (`DriverRegistry`) already carries this as an in-process singleton; no
   separate aggregate was needed. A RuntimeAggregate would formalize `runtimeId`,
   `epoch`, and `startedAt` as authoritative events.

2. **Epoch behavior.** M0-B reconciliation and replay are driven by the event
   ledger's global sequence, not a runtime epoch. A restart is observable purely
   as a gap in `driverRun` stream events. A RuntimeAggregate could record an
   explicit `RuntimeRestarted` event with a new epoch counter, improving
   reconciliation clarity — but it is not required for correctness today.

3. **Driver registry lifecycle.** `DriverRegistry` is the only cross-run state
   that survives a process restart in M0-B (it is rebuilt from the descriptor
   store). This is genuinely runtime-scoped, not mission/task scoped. It is the
   strongest candidate for RuntimeAggregate ownership.

4. **Schema compatibility requirements.** Driver descriptors declare
   `contractSchemaVersion` and `driverVersion`. The registry already validates
   these. A RuntimeAggregate would centralize "which schema versions are
   currently accepted by this runtime instance."

5. **Policy bundle identity.** M0-B deliberately kept the policy engine OUT of
   the driver trust boundary (ADR-0120). No runtime-wide policy bundle identity
   was needed. If M0-C introduces multiple drivers or dynamic policy, this becomes
   relevant.

6. **Restart count usefulness.** The M0-B acceptance scenario restarts the
   runtime and reconciles without re-execution. A restart counter would be a
   convenience metric, not a correctness primitive.

7. **Checkpoint lineage.** Checkpoints are per-aggregate (DriverRunAggregate
   checkpoints its own state). No runtime-wide checkpoint lineage was required.

8. **Replay lineage.** Full replay + checkpoint-plus-tail replay are proven
   equivalent at the ledger level. RuntimeAggregate would add no new replay
   semantics.

9. **Runtime health states.** M0-B defines driver health (registry
   enabled/disabled) but no runtime health state. A `RuntimeHealth` enum
   (healthy/degraded) would be a RuntimeAggregate concern if M0-C needs degraded
   mode.

10. **Degraded-mode semantics.** Not exercised by M0-B. Deferred.

11. **Driver compatibility metadata.** Captured per-descriptor today. A
    RuntimeAggregate could index it, but the registry already serves it.

12. **What is genuinely authoritative runtime-wide state.** Only two things are
    runtime-scoped and authoritative: (a) the set of registered/disabled drivers,
    and (b) the runtime identity/epoch. Everything else is mission/task/driver-run
    scoped and already owned by the correct aggregate.

13. **What would duplicate existing aggregate ownership.** Capability grants
    (CapabilityAggregate), claims (ClaimAggregate), task state (TaskAggregate),
    mission state (MissionAggregate), driver-run state (DriverRunAggregate). A
    RuntimeAggregate must NOT re-own any of these or it violates ADR-0103
    (aggregate ownership).

## Recommendation

**REVISE THE PROPOSAL, then implement a minimal RuntimeAggregate after M0-B.**

Rationale:
- The evidence shows only a *narrow* slice of state is genuinely runtime-scoped
  (driver registry lifecycle + runtime identity/epoch). The original Treasure
  Chest proposal likely over-scoped RuntimeAggregate.
- Implement it only after M0-B is merged, and limit it to: `runtimeId`,
  `epoch`, `startedAt`, `RuntimeRestarted` events, and ownership of the
  `DriverRegistry` lifecycle (register/disable/unregister as authoritative
  events). It must NOT touch capability/claim/task/mission/driver-run state.
- Defer `RuntimeHealth`/degraded-mode until M0-C demonstrates the need.

This keeps the trust boundary intact (ADR-0103, ADR-0120) and avoids duplicate
aggregate ownership.

## Proposed change to Treasure Chest issue

If a Treasure Chest issue tracks RuntimeAggregate, update it to:
- Narrow scope to {runtimeId, epoch, DriverRegistry lifecycle}.
- Mark M0-B as the evidence source (this document).
- Remove any capability/claim/task/mission ownership from the proposal.
- Gate implementation on M0-B merge + a separate post-M0-B authorization (per
  mission: "Do not implement RuntimeAggregate without a separate post-M0-B
  authorization").
