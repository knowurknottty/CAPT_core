# CAPT Desktop Runtime — Contract Map

Authoritative SHA: `sha1:6b3f769cc1042428d758aade443cc6009ce6a2b9`.

Every desktop surface maps to an existing CAPT command, query, event, or
contract. No parallel domain model is introduced. Where a new public contract
would be required, it is flagged with proven-missing + ADR (none required for
M0 read-only).

## Desktop surface → CAPT interface

| Desktop surface | CAPT command / query / event | Existing interface | Gap | Adapter | Authority owner |
|---|---|---|---|---|---|
| Runtime identity/version | `RuntimeService`/`EventStore` read | `EventStore.head_sequence()`, `head_chain()`, `capt_runtime.RUNTIME_VERSION`, `contracts` schema `1.0.0` | none | `RuntimeQueryService.identity()` | CAPT |
| Connection health | ledger integrity | `EventStore.verify_chain()` | none | `identity().integrity` | CAPT |
| MissionSpec | `MissionCreated` event / aggregate state | `EventStore.load_state("mission-<id>")` | none | client `get_state` | CAPT |
| TaskGraph | `TaskCreated`/`TaskTransitioned` | `EventStore.load_state("task-<id>")` | none | client `get_state` | CAPT |
| DriverRun | `DriverRunCreated`/`DriverRunStateChanged` | `EventStore.load_state("driverrun-<id>")` | none | client `get_state` | CAPT |
| Capability scopes (grant+lease) | `CapabilityGranted`/`CapabilityLeaseActivated` | `EventStore.load_state("capability-<grantId>")` (lease nested under `lease`) | none | client `get_state` | CAPT |
| Event timeline | all events | `EventStore.read_events(after)` | none | client `event_timeline` | CAPT |
| Evidence | verification checks | `capt_runtime.verification.build_verification_result` | none (computed server-side) | `RuntimeQueryService.verification()` | CAPT |
| Verification result | `VerificationResult` | `build_verification_result` | none | `verification()` query | CAPT |
| ClaimGuard disposition | `ClaimRecord` + `guard_claim` | `capt_runtime.verification.guard_claim` | none (computed server-side) | `RuntimeQueryService.claimguard()` | CAPT |
| Aggregate inventory | all aggregates | `EventStore.all_aggregates()` | none | `list_aggregates()` | CAPT |
| Stream events | per-stream events | `EventStore.read_stream(<id>)` | none | `get_stream_events` | CAPT |

## IPC query contract (new, internal to M0)

A new *transport* contract is introduced, but it carries **no new CAPT domain
model** — it is a thin read-query envelope over existing aggregates:

```
request  = { "op": <op>, ...op-specific-fields }
response = { "ok": true, "result": <existing CAPT contract-shaped value> }
          | { "ok": false, "error": <string> }
ops: identity | list_aggregates | get_state | get_stream_events
   | event_timeline | claimguard | verification
```

Each `result` is an existing CAPT contract-shaped object (MissionSpec,
TaskNode, DriverRun, CapabilityGrant state, EventEnvelope, VerificationResult,
ClaimGuard verdict). No new aggregate, event type, or schema was added.

## Generated bindings reuse
- `contracts/generated/python/capt_contracts` is importable and used by Gate0
  (`generated_contracts_available` PASS). The client may adopt the generated
  Python validator for request/response shapes in a later cleanup; M0 relies on
  the server-side `require(...)` contract validation that already guards every
  authoritative write.

## New public contract required?
- **None** for M0. All desktop reads map to existing CAPT read APIs. If M1 adds
  a desktop-originated *command* (e.g. create mission from the UI), that will
  require: proven missing function, ADR, schema version analysis, generated
  binding strategy, and conformance tests — per workflow Gate 4.
