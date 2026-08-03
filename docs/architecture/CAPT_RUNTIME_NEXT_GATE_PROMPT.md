# CAPT Runtime — Next Program Gate Prompt

Date: 2026-08-03
Context: M0 stack frozen and verified (M0-A PROVEN, M0-B PROVEN, freeze PASSED).
Integration artifacts prepared; merge pending owner authorization. M0-C,
RuntimeAggregate, RuntimeManifest, and external-driver integration have NOT started.

## Gate evaluation (based on integrated evidence)

| Gate | Description | Dependency / risk | Recommendation |
|------|-------------|-------------------|----------------|
| A — External ExecutionDriver conformance proof | Prove a real external harness can implement the frozen driver contract without changing CAPT authority semantics. | Depends on M0-B freeze being stable (it is). Low risk; validates the boundary against a real external implementation. | **Primary candidate** — directly exercises the frozen contract's portability claim. |
| B — Governed repository-write proof (M0-C) | Isolated worktree write, tests, evidence, checkpoint, truthful claim, no push. | Larger scope; introduces write authority (the next authority class after read-only). Higher risk. Should follow a validated external-driver boundary. | Defer until A validates the boundary. |
| C — Runtime bootstrap identity specification | Define (not necessarily implement) minimal immutable runtime startup record. | Depends on demonstrated need; ADR proposal already recommends RuntimeManifest. Low urgency (deferred in M0). | Parallel non-blocking maintenance candidate. |
| D — Release Security CI remediation | Split required vs optional security jobs (already recommended). | Unblocks CI green; environmental, not product. Independent of runtime scope. | **Parallel non-blocking maintenance gate** — can run anytime. |

## Recommended next primary gate: Gate A — External ExecutionDriver conformance proof

**Why:** The M0-B freeze establishes a precise, verified driver contract and proves
it with a *local CAPT reference driver*. The single largest untested claim is
portability: that a *real external* harness can implement the same contract without
altering CAPT authority semantics. Gate A closes that gap using the frozen contract
(already inventoried and version-locked at 1.0.0) and the existing conformance
suite (51 M0-B tests) as the baseline. It requires no contract change and no new
authority — only an external adapter that satisfies the frozen input/output
boundary. This is lower-risk than M0-C (which introduces write authority) and
logically precedes it.

**Preconditions:** M0 stack merged to main (or at minimum M0-B + freeze accepted).
Contract version 1.0.0 frozen. Driver boundary doc
(`CAPT_RUNTIME_M0_DRIVER_BOUNDARY.md`) already specifies the future external-driver
conformance requirement (unimplemented).

## Parallel non-blocking maintenance gate: Gate D — Release Security CI remediation

**Why:** The "Release Security" private-dependency failure is pre-existing and
environmental; it blocks a fully-green CI but not M0 acceptance. Splitting required
vs optional security jobs (recommendation from
`RELEASE_SECURITY_DEPENDENCY_DECISION.md`) is independent of runtime scope and can
proceed in parallel without affecting the M0 freeze.

## Explicitly deferred

- **Gate B (M0-C):** defer until Gate A validates the external-driver boundary.
  M0-C introduces write authority and is the next major authority class; it must
  build on a proven, portable read-only boundary.
- **Gate C (RuntimeManifest):** deferred; only implement if integration evidence
  demonstrates need. ADR proposal already scopes it minimally.

## Prepared prompt for Gate A (do NOT execute in this mission)

```
You are continuing the CAPT Runtime / Agent Harness program. M0 (M0-A + M0-B) is
frozen and verified; the ExecutionDriver contract is version-locked at 1.0.0 and
documented in CAPT_RUNTIME_M0_DRIVER_BOUNDARY.md / CAPT_RUNTIME_M0_CONTRACT_INVENTORY.md.

Mission: Gate A — External ExecutionDriver conformance proof.
Prove a REAL external harness can implement the frozen driver contract WITHOUT
changing CAPT authority semantics.

Do NOT modify contracts (1.0.0 frozen) unless a proven defect requires it.
Do NOT widen driver authority. Do NOT implement M0-C, RuntimeAggregate,
RuntimeManifest, or RuntimeIdentity. Do NOT merge M0.

Steps:
1. Select a real external harness (e.g. a genuine installed agent framework) that
   is NOT the CAPT reference driver.
2. Implement an adapter that maps the external harness's execution loop onto the
   frozen ExecutionDriver input/output contract (bounded work order, context slice,
   scoped leases, filesystem/network policy, budgets, expected artifacts, required
   receipts, termination conditions -> untrusted observations/artifacts/receipts/
   progress/diagnostics/claim proposals).
3. Run the existing M0-B conformance suite (tests/capt_runtime/test_m0b_driver.py)
   against the external adapter; all 51 tests must pass unchanged (no contract edit).
4. Add adversarial tests proving the external adapter cannot: mutate Mission/
   Task/Capability/Claim aggregates, append EventLedger, issue CapabilityGrants/
   Leases, create VerificationResults/ClaimGuardDecisions, or mark completion.
5. Prove no external OpenHarness/CAPT types leak into CAPT public contracts.
6. Record exact commands, exit codes, counts, and log paths. Do not carry forward
   prior counts without fresh output.
7. If the external harness cannot satisfy the contract without a contract change,
   STOP and report the gap — do NOT silently widen the contract.

Deliver: external-driver conformance report + adapter code on a dedicated branch +
draft PR. End with M0_EXTERNAL_DRIVER_CONFORMANCE_PROVEN or
M0_EXTERNAL_DRIVER_CONFORMANCE_BLOCKED.
```
