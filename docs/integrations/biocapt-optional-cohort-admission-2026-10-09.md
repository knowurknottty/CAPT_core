# CAPT Core — bioCAPT optional cohort admission (October 9, 2026)

Branch introduces `capt_runtime.biocapt_cohort_reader.BioCAPTLocalCohortReader`.

## Implemented
Read-only Unix-socket manifest/snapshot observer, using bioCAPT's existing
`biocapt.live-introspection/1` transport. Requires a CAPT EventStore-persisted,
currently active, subject/mission/task-bound filesystem-read capability lease
whose path scope includes the private Unix socket. Refuses missing, expired,
revoked, bounded-use and unsupported-condition grants. Verifies private socket
ownership/mode, validates schema, process state and both poll and cogitation
freshness. Reports typed NO_VOTE, SKIPPED, PROPOSED, CONVERGED, DIVERGENT,
UNHEALTHY, UNKNOWN and advisory-only evidence digest without propagating
private prompts, memory or language content. Zero model dispatches.

## Critical boundaries
This is a **real read-only observer**, not yet a cognitive execution adapter.
No new CAPT capability is granted/activated by merely importing it; no
RuntimeService mutation is performed. Observed CONVERGED does not mean verified
truth or an approved action. It does not change any vessel scheduling.

CAPT's ordinary CohortDispatcher compiles each cohort into one governed
provider invocation; legacy VesselDispatcher can dispatch per vessel and must
not be used as an implicit replacement for logical-vessel semantics.

## Measured
Focused real CAPT capability/cohort tests plus new denied-grant tests:
18 passed in 0.26 seconds, CAPT Node operation
`remote-capt-20261009T123339Z-10edc1ce`.
Python file compiled. Positive authorized-lease/live-source end-to-end test
**not yet run**. Hence only opt-in source integration, not production accepted.

## Blockers requiring governed follow-through
1. Node's current capability roots exclude the live bioCAPT directory.
   The operator may explicitly authorize an appropriately narrow grant;
   no scope enlargement or HumanApproval override was attempted.
2. Add bioCAPT-side authenticated local cognitive request entrypoint with
   idempotency, budget, cancellation, outcome reconciliation and receipts,
   then a CAPT DriverHost-bound adapter. The current live endpoint is
   intentionally GET-only.
3. Run genuine persisted-grant positive conformance, live Unix-socket
   observation, full native cogitation and desktop acceptance before
   treating bioCAPT as an operational CAPT cognitive cohort.
4. Keep DeepSeek interpretation downstream of raw/native evidence and
   never let model prose authorize CAPT actions.
