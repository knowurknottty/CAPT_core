# External Driver Trust Boundary (Gate A — OpenHarness)

## Principle

CAPT is the ONLY system allowed to create authoritative state. The external
OpenHarness harness is untrusted. It may return only:

- `DriverObservation` (untrusted analysis text)
- `DriverArtifactCandidate` (artifact in CAPT staging, digest-verified)
- `DriverReceiptCandidate` (external execution receipt)
- `DriverProgressSignal` (ephemeral; not used in this proof)
- diagnostics / external run identifiers

It MUST NOT emit:

- `PolicyDecision`, `CapabilityGrant`, `CapabilityLease`, `CapabilityConsumptionRecord`
- aggregate state changes (Mission/Task/Capability/Claim)
- `EventEnvelope`, `EvidenceRecord`
- `VerificationResult`, `ClaimGuardDecision`
- task/mission completion claims

## What the harness receives (minimized)

- A bounded `ExecutionDriverWorkOrder` + `ContextSlice` (no GovernanceKernel,
  PolicyEngine, ClaimGuard, CapabilityAggregate, EventLedger, or other mission
  state).
- A read-only target repository path (no write authority).
- A CAPT-owned staging directory (the only place an artifact may land).
- A localhost Ollama endpoint + local model (no hosted provider, no credentials).

## What the harness is denied

- unrestricted home-directory access (sandboxed config dir only),
- CAPT database / event-ledger handles,
- credential stores (all hosted keys stripped),
- global environment variables (only a minimal allowlist forwarded),
- unrelated repository paths,
- unrelated memory / full conversation history,
- raw policy bundles,
- unrestricted network access (only 127.0.0.1:11434).

## Enforcement layers

1. **Contract schema** (`require`): the work order and all driver records are
   validated against the frozen 1.0.0 schemas. `DriverObservation.trust` must be
   `untrusted` (enforced at schema level).
2. **Ingestion validation** (`ingestion.py`): rejects impersonation
   (`observedBy` mismatch), cross-mission output, duplicate conflicts, path/symlink
   escapes, digest mismatch, and any fabricated authoritative type
   (`reject_fabricated_authoritative`).
3. **Capability lease** (`capability.py`): re-validated immediately before dispatch
   — identity, mission/task, active status, operation coverage, path scope, budget.
4. **Subprocess sandbox** (`sandbox.py`): allowlisted env; hosted keys removed;
   only localhost Ollama reachable.

## Context minimization

The `ContextSlice` passed to the harness contains only: lease (id/scoped paths/
validity), filesystem policy (read-only), permitted tools, budgets, expected
artifacts, termination conditions. No governance/policy/claim/ledger references.
A context-over-disclosure test (sentinel authority objects) is covered by the
adversarial suite at the ingestion layer.

## Known boundary limitations

- `verify_lease` does not enforce max-use exhaustion (frozen M0-B gap; see
  SECURITY_REVIEW). All other lease checks (revoked/expired/scope/mission/task/
  driver/operation) are enforced.
- The harness binary is third-party code; it is run with least authority but not
  formally audited. Mitigated by isolation + read-only task + digest proof.
