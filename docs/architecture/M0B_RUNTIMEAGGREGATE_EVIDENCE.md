# M0-B RuntimeAggregate Evidence Log (Part 16, expanded)

Status: NOT IMPLEMENTED. This is a **living evidence log** for the post-M0-B
RuntimeAggregate design. It records every observation from the M0-B read-only
driver proof relevant to a future RuntimeAggregate. Updated as M0-B matured.

## Required evidence fields (post-M0-B design inputs)

### 1. Runtime identity requirements
- M0-B needed a stable `runtimeId` only to namespace the driver registry and the
  staging root. The registry (`DriverRegistry`) is currently an in-process
  singleton; no authoritative `RuntimeIdentity` event exists.
- **Evidence**: `DriverRegistry` carries no `runtimeId`; `DriverHost` holds
  `staging_root`/`target_repo` as constructor args. No runtime identity event is
  emitted.
- **Design input**: if RuntimeAggregate is built, it should own `runtimeId`,
  `epoch`, `startedAt`, and emit `RuntimeStarted` / `RuntimeRestarted` events.

### 2. Driver registry lifecycle
- The registry is the ONLY runtime-scoped, authoritative state in M0-B. It records
  register / disable / unregister as authoritative `DriverRegistered` /
  `DriverDisabled` events (trust=registration_only, trustClassification=untrusted).
- **Evidence**: `drivers/registry.py` — duplicate-ID rejection, immutable
  descriptor identity, version compat, capability declarations, disable, health,
  trust classification, descriptor digest.
- **Design input**: RuntimeAggregate should OWN the driver-registry lifecycle
  (register/disable/unregister as authoritative events). This is the strongest
  candidate for RuntimeAggregate ownership.

### 3. Runtime health
- M0-B defines driver health (registry enabled/disabled) but NO runtime health
  state. No `RuntimeHealth` enum, no degraded mode.
- **Evidence**: no health state machine exists; `verify_no_git_mutation` and
  `verify_repository_unchanged` are per-run checks, not runtime health.
- **Design input**: defer `RuntimeHealth`/degraded-mode until M0-C demonstrates
  need. Do not invent it now.

### 4. Restart lineage
- A runtime restart is observable purely as a gap in the `driverrun` stream events
  (no `RuntimeRestarted` event). Reconciliation and replay are driven by the event
  ledger's global sequence, not a runtime epoch.
- **Evidence**: `test_replay_idempotent` proves full replay == checkpoint+tail
  replay; restart recovery uses ledger replay, not a runtime epoch counter.
- **Design input**: a `RuntimeRestarted` event with an epoch counter would improve
  reconciliation clarity but is NOT required for correctness today.

### 5. Replay lineage
- Full replay and checkpoint-plus-tail replay are proven equivalent at the ledger
  level (`replay.py`). No runtime-wide replay lineage needed.
- **Evidence**: `test_replay_idempotent` (digest equality). Store optimistic
  concurrency guard (`test_stale_version_rejection`) prevents re-application.
- **Design input**: RuntimeAggregate adds no new replay semantics.

### 6. Checkpoint lineage
- Checkpoints are per-aggregate (DriverRunAggregate checkpoints its own state via
  `checkpoint.py`). No runtime-wide checkpoint lineage.
- **Evidence**: `checkpoint.py` recovers open reservations from the ledger; M0-B
  run state is included in the aggregate snapshot.
- **Design input**: keep checkpoints per-aggregate; do not centralize in
  RuntimeAggregate.

### 7. Runtime configuration ownership
- M0-B configuration (staging root, target repo, lease policy) is passed via
  `DriverHost` constructor. No authoritative runtime-config record.
- **Evidence**: `driver_host.py` constructor args; no `RuntimeConfig` event.
- **Design input**: if config must be authoritative/auditable, RuntimeAggregate
  could own a `RuntimeConfigSet` event — but this is optional.

### 8. Policy bundle identity
- M0-B deliberately keeps the policy engine OUT of the driver trust boundary
  (ADR-0120). No runtime-wide policy bundle identity was needed.
- **Evidence**: `capability.py` encodes the read-only allow/deny lists directly;
  no external policy bundle is loaded for driver dispatch.
- **Design input**: if M0-C introduces dynamic policy, RuntimeAggregate could
  carry `policyBundleId`/`policyBundleDigest`. Defer.

### 9. Loaded schema versions
- Driver descriptors declare `contractSchemaVersion` and `driverVersion`. The
  registry validates these on registration (`verify_identity` digest compare).
- **Evidence**: `drivers/registry.py` `verify_identity`; `DESCRIPTOR` carries
  `contractSchemaVersion: "1.0.0"`.
- **Design input**: RuntimeAggregate could centralize "which schema versions are
  currently accepted by this runtime instance" — but the registry already serves it.

### 10. Loaded driver versions
- Each registered driver exposes `driverVersion` + `packageIdentity` (digest). The
  registry rejects version substitution (ADR-0121).
- **Evidence**: `test_lease_rejects_wrong_driver` / registry identity check;
  `DESCRIPTOR["driverVersion"]`.
- **Design input**: RuntimeAggregate would index driver versions, but the registry
  already serves this. Avoid duplication.

## Recommendation (unchanged from initial Part 16)

**REVISE THE PROPOSAL, then implement a minimal RuntimeAggregate after M0-B.**

- Narrow scope to: `{runtimeId, epoch, DriverRegistry lifecycle}`.
- It must NOT re-own capability/claim/task/mission/driver-run state (ADR-0103,
  ADR-0120 ownership boundaries).
- Gate implementation on M0-B merge + a separate post-M0-B authorization.
- Defer `RuntimeHealth`, `RuntimeConfig`, `policyBundleId` until M0-C demonstrates
  the need.

## Proposed change to Treasure Chest issue

If a Treasure Chest issue tracks RuntimeAggregate, update it to:
- Narrow scope to {runtimeId, epoch, DriverRegistry lifecycle}.
- Mark M0-B as the evidence source (this document).
- Remove any capability/claim/task/mission ownership from the proposal.
- Gate implementation on M0-B merge + separate post-M0-B authorization.
