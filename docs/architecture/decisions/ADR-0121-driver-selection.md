---
status: Accepted (M0-B)
date: 2026-08-03
relates_to: mission Part 4, ADR-0120
---

# ADR-0121 — ExecutionDriver selection

## Context
The mission specifies a priority order: (1) OpenHarness, (2) DeepAgents,
(3) OpenAI Agents SDK. M0-B supports exactly one driver.

## Candidate scoring (read-only proof fitness)

| Candidate | read-only | tool restrict | context isolate | lifecycle obs | cancel | suspend/resume | checkpoint/reconcile | local-model | py compat | license | thin adapter | framework-ownership risk | install burden | testable |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| OpenHarness | High (inspect/index/analyze) | High (no write primitives) | High | Medium | Medium | Medium | Medium | High | High | Permissive | High | Low | Low | High |
| DeepAgents | Low (exposes file-write/shell) | Medium | Medium | Medium | Medium | Medium | Medium | Medium | High | MIT | Medium | Medium (agentic affordances) | Medium | Medium |
| OpenAI Agents SDK | Low (network egress + tool-calling) | Medium (runtime policy) | Medium | High | High | High | Medium | Medium | High | MIT | Medium | Medium | Low | Medium |

## Decision
Select **OpenHarness**. It is read-only by construction: repository inspection,
filesystem reads, code indexing, and analysis. Its contract surface exposes no
mutation primitives (no write/shell/git/commit/push/deploy), which makes the
untrusted-external-driver trust boundary straightforward to prove.

## Rejected alternatives
- **DeepAgents**: agentic frameworks routinely expose file-write and shell
  tools; proving a strict read-only boundary would require disabling affordances,
  adding surface for capability bypass. Deferred.
- **OpenAI Agents SDK**: defaults to network egress and tool-calling that can
  mutate external state; the read-only proof would depend on runtime policy, not
  contract shape. Deferred.

## Consequences
- One driver implementation: `OpenHarnessDriver`.
- The `ExecutionDriver` interface is driver-agnostic; a later gate can add
  another driver without changing the trust boundary.
- No multi-driver support in M0-B (explicitly excluded).

## Reversal conditions
If OpenHarness cannot be installed/run in the verification environment, fall back
to a simulated `OpenHarnessDriver` that honors the same contract (still
read-only). Selection of a different driver requires a new ADR.

## License
OpenHarness: permissive (MIT/Apache-2.0 class). Compatible with CAPT.

## Integration surface
`capt_runtime/drivers/openharness.py` implements `ExecutionDriver`. The driver
receives a `ContextSlice` + `ExecutionDriverWorkOrder`; returns untrusted
`DriverObservation`/`DriverArtifactCandidate`/`DriverReceiptCandidate`.

## Trust boundary
Driver process is untrusted; all outputs validated by `capt_runtime/verification.py`
before any authoritative record is created.
