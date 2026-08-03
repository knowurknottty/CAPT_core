# Hermes Trust Boundary

## Position of the boundary

The boundary is the **OS process boundary**. Everything inside the `hermes`
process is untrusted. Everything CAPT does with its output is authoritative.

```
┌─────────────────────── CAPT (authoritative) ────────────────────────┐
│ GovernanceKernel · PolicyEngine · CapabilityAggregate · EventLedger │
│ ClaimGuard · VerificationService · DriverRunAggregate · Checkpoints │
│                                                                     │
│   DriverHost ──► verify_lease ──► HermesDriver.submit               │
│                                        │                            │
└────────────────────────────────────────┼────────────────────────────┘
                                         │  argv + minimal env + cwd
                                         ▼  (shell=False, no secrets)
                        ┌────────────── hermes process ──────────────┐
                        │ UNTRUSTED. Own model turn, own tool loop.  │
                        │ No CAPT handles. No DB. No ledger.         │
                        └────────────────────┬───────────────────────┘
                                             │  stdout (text only)
┌────────────────────────────────────────────▼────────────────────────┐
│ reject_forged_authority ──► DriverObservation(trust=untrusted)      │
│   ──► ingestion validation ──► independent verification             │
│   ──► ClaimGuard ──► EvidenceRecord ──► checkpoint                  │
└─────────────────────────────────────────────────────────────────────┘
```

## What Hermes may return

* `DriverObservation` (always `trust: untrusted`)
* `DriverArtifactCandidate` (CAPT confirms existence and digest)
* `DriverReceiptCandidate`
* `DriverProgressSignal`
* `DriverClaimProposal`
* diagnostics (pid, exit code, elapsed, stderr tail)
* external run identifiers

## What Hermes may never authoritatively create

`PolicyDecision` · `CapabilityGrant` · `CapabilityLease` ·
`CapabilityConsumptionRecord` · `EventEnvelope` · Mission or Task state ·
`EvidenceRecord` · `ClaimRecord` · `VerificationResult` · `ClaimGuardDecision` ·
completion state.

Enforcement: `reject_forged_authority()` scans stdout for authoritative markers
before an observation is constructed, and `capt_runtime.ingestion` rejects
forged types structurally. Both layers are tested
(`test_forged_authoritative_output_rejected`, six parametrised cases).

## What Hermes never receives

| Withheld | Mechanism |
|---|---|
| GovernanceKernel, ClaimGuard, EventLedger | never imported into the child; no handle can cross argv |
| Aggregate repositories, DB handles | not passed; child has no CAPT import path |
| Full policy bundle | prompt is derived **only** from the ContextSlice |
| Unrelated memory / other missions | ContextSlice is per-run and minimal |
| Raw secrets | `minimal_env()` allow-list + credential-name denylist |
| Network egress | `networkPolicy.egressAllowed: false`; toolset excludes web/browser |
| Write capability | `writesAllowed: false`; write-capable slice refused outright |

`test_prompt_derives_only_from_context_slice` asserts that none of
`GovernanceKernel`, `ClaimGuard`, `EventLedger`, `policyBundle`,
`policyDecisionId`, `grantId`, `aggregate`, or `capt_authoritative` appear in the
prompt.

`test_minimal_env_excludes_credentials` sets `MY_API_KEY`, `SOME_TOKEN`, and
`AUTH_SECRET` in the parent and asserts none reach the child, by name or value.
`test_minimal_env_refuses_credential_shaped_extra` asserts the adapter raises
rather than forward a credential-shaped variable even when asked explicitly.

## Containment posture (honest statement)

Mode A enforces containment **ex ante** and **ex post**, not per-tool-call:

Ex ante — capability lease revalidated immediately before dispatch; read-only
filesystem policy; egress disabled; single-tool toolset; `--safe-mode`; cwd
pinned; minimized env; wall-clock budget with SIGKILL on overrun.

Ex post — target tree digest compared before and after; artifact must resolve
inside the staging root via `realpath` (defeats symlink escape); artifact digest
must match; observation `observedBy` must match the registered driver identity;
forged authoritative markers rejected; ClaimGuard bounds what may be asserted.

CAPT does **not** intercept each tool call inside the Hermes loop. That capability
belongs to Mode B and is explicitly out of scope here.
