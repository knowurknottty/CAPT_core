# ADR Proposal: Post-M0-B RuntimeAggregate (deferred, minimal scope)

Status: PROPOSAL (not implemented). Do NOT implement RuntimeAggregate in M0-B or
this pass. This document defines the smallest viable design for a future,
separately-authorized effort.

## Context

M0-B established a read-only ExecutionDriver proof. The only runtime-scoped
authoritative state it introduced is the `DriverRegistry` (register/disable/
unregister lifecycle). No `RuntimeIdentity`, `RuntimeEpoch`, `RuntimeHealth`,
`RuntimeConfig`, or `policyBundleId` exists. Replay/checkpoint are per-aggregate
and ledger-driven. The question: is a `RuntimeAggregate` justified now?

## Decision

**RuntimeAggregate is NOT yet justified as a new aggregate.** The only concrete,
evidence-backed ownership gap is the driver-registry lifecycle, which is already
served by `DriverRegistry`. A full RuntimeAggregate would duplicate state already
owned elsewhere.

**Recommended architecture: Option 4 — `DriverRegistry` plus checkpoint metadata,
augmented by a minimal `RuntimeManifest` (not a new aggregate).**

If a RuntimeAggregate is later authorized, its scope MUST be the smallest viable:

### Smallest viable scope (if implemented)
```
RuntimeAggregate owns ONLY:
  - runtimeId            (stable instance identity)
  - epoch                (monotonic restart counter; RuntimeRestarted event)
  - DriverRegistry lifecycle events (DriverRegistered / DriverDisabled /
    DriverUnregistered) — promoted from DriverRegistry's audit log to
    authoritative RuntimeAggregate events
```

### Explicitly EXCLUDED from RuntimeAggregate
- mission lifecycle (MissionAggregate)
- task lifecycle (TaskAggregate)
- capability lifecycle (CapabilityAggregate)
- driver-run lifecycle (DriverRunAggregate)
- claims (ClaimAggregate)
- evidence / verification results
- memory content
- tool results
- external harness authority

### Deferred fields (do NOT add until a concrete need is demonstrated)
- `RuntimeHealth` / degraded-offline status → defer to M0-C
- `RuntimeConfigSet` → optional; config currently via DriverHost constructor
- `policyBundleId` / `policyBundleDigest` → defer to M0-C dynamic policy
- `loadedSchemaVersions` / `loadedDriverVersions` → already served by
  DriverRegistry; do not duplicate

## Alternatives considered

1. **RuntimeAggregate (full).** Rejected: would duplicate DriverRegistry,
   checkpoint, and replay ownership; violates single-source-of-truth.
2. **RuntimeManifest + immutable startup record.** ACCEPTED as the preferred
   shape: a `RuntimeManifest` (runtimeId, epoch, startedAt, config digest,
   loaded schema/driver versions snapshot) emitted once at startup, plus a
   `RuntimeRestarted` event on recovery. No new mutable aggregate needed for
   M0-B/M0-C readiness.
3. **RuntimeEpoch aggregate.** Rejected: epoch is one field, not an aggregate.
4. **DriverRegistry + checkpoint metadata.** ACCEPTED as the mechanism that
   already covers registry lifecycle; RuntimeManifest adds only identity+epoch.
5. **No new aggregate yet.** ACCEPTED as the current state; RuntimeAggregate is
   premature.

## Consequences

- No new aggregate is introduced in M0-B. The evidence log
  (`M0B_RUNTIMEAGGREGATE_EVIDENCE.md`) stands as the design input.
- If M0-C demonstrates need for runtime health / dynamic policy, revisit with the
  narrow scope above and a separate authorization.
- Treasure Chest issue "Post-M0-B CAPT RuntimeAggregate" should be updated to the
  narrow scope `{runtimeId, epoch, DriverRegistry lifecycle}` and gated on M0-B
  merge + separate post-M0-B authorization.

## Triple-recursion (Construct / Adversarial / Reconcile)
- **Construct:** surveyed 12 evidence fields; found only registry lifecycle is
  unowned-by-an-aggregate today, and even that is served by DriverRegistry.
- **Adversarial:** tested whether each proposed field is "truly runtime-global
  authoritative" vs "derivable/observational/duplicated/config". Health, config,
  policy → deferred (no demonstrated need). Schema/driver versions → already in
  registry (duplication risk). Only runtimeId + epoch + registry events survive.
- **Reconcile:** recommend RuntimeManifest (not a new aggregate) as the minimal
  honest design; full RuntimeAggregate only if separately authorized with the
  excluded-list enforced.
