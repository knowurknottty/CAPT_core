# ADR: Hermes Integration Mode

Status: Accepted
Date: 2026-08-03
Supersedes: none
Relates to: ADR-0110 (trust families), ADR-0120 (ExecutionDriver), ADR-0122
(capability leases), ADR-0125 (context minimization), ADR-0126 (ingestion)

## Context

Hermes must participate in CAPT-governed work. Three modes were considered.

**Mode A — Hermes as external ExecutionDriver.** CAPT launches a real Hermes
process with a bounded work order and ingests its output as untrusted.

**Mode B — Bootstrap-bridge ownership.** Hermes runs the loop; its model turns
are forwarded over an authenticated socket to a CAPT Agent Runner, and direct
Hermes model execution is suppressed.

**Mode C — Hybrid.** CAPT owns mission/authority semantics; Hermes runs a bounded
internal loop beneath one CAPT DriverRun.

An earlier direction favoured Mode B. That preference was re-evaluated against the
actual code, not carried forward.

## Evidence gathered

1. The frozen M0 baseline (`capt-runtime-m0`) already defines a complete,
   contract-validated external boundary: `ExecutionDriver`, `DriverRegistry`,
   `DriverRunAggregate`, `DriverHost`, `ContextSlice`, capability leases,
   ingestion, verification, ClaimGuard, checkpoint/replay, reconciliation.
2. The bootstrap bridge lives only on the unmerged
   `origin/feature/capt-bootstrap-bridge` branch. It is not in `main` and not
   part of the frozen baseline.
3. Mode B requires Hermes-side middleware to suppress direct model execution.
   That places the Hermes process inside the CAPT trust boundary and makes CAPT
   dependent on a Hermes-internal hook remaining stable across upgrades — the
   installed runtime is already 753 commits behind upstream.
4. Mode B introduces a second authority path (socket protocol, turn IDs, runner
   lifecycle, authentication) that must be defended independently of the frozen
   driver boundary. That is a duplicate ownership boundary.
5. Mode A needs no new wire contract. The Hermes driver validates against the
   existing frozen `ExecutionDriverDescriptor` and `ExecutionDriverWorkOrder`
   schemas with zero contract edits.

## Decision

**Mode A.** Hermes is an external, untrusted ExecutionDriver.

CAPT launches the real `hermes` executable with `shell=False`, an explicit argv
list, a minimized environment, a read-only working directory, and a wall-clock
budget derived from the ContextSlice. Hermes stdout is ingested as a
`DriverObservation` with `trust: untrusted`. CAPT alone writes the staging
artifact, verifies it, and decides what may be claimed.

## Consequences

Positive:

* No new wire contract. No frozen contract change. `contracts/` is byte-identical.
* No second authority path. One owner per model turn: Hermes owns its own internal
  model call; CAPT owns whether that process runs at all, with what capability,
  over what paths, for how long, and which of its outputs become authoritative.
* Hermes upgrades cannot silently break CAPT governance — the boundary is the OS
  process boundary, not a Hermes-internal hook.
* Removal is trivial and provable: delete one module.

Negative / accepted limits:

* CAPT does not intercept Hermes' individual model calls. Hermes performs its own
  model turn internally. CAPT's authority is over the bounded delegation, not over
  each token. This is stated explicitly in `HERMES_MODEL_TURN_OWNERSHIP_TRACE.md`
  and is **not** claimed to be per-turn interception.
* Per-tool-action revalidation inside the Hermes loop is not available in Mode A.
  Containment is enforced ex ante (capability lease, read-only slice, minimized
  env, no egress, restricted toolset, cwd pinned to the target) and ex post
  (tree digest before/after, staging-path enforcement, forged-authority
  rejection).

If per-model-turn interception is later required, Mode B becomes justified and
must be adopted through a new ADR with its own conformance proof. It is not
adopted here.
