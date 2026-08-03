# CAPT Desktop Runtime — Implementation Roadmap

Authoritative SHA: `sha1:6b3f769cc1042428d758aade443cc6009ce6a2b9`.

Milestones follow the authoritative workflow Gate 5. M0 is implemented and
proven in this change. M1–M3 are scoped but NOT implemented here (stop rule).

## Desktop M0 — Operator shell and runtime connection  ✅ DONE (this change)
Deliverables:
- `desktop/capt_runtime_service.py` — local CAPT runtime service (authoritative side)
- `desktop/desktop_runtime_client.py` — authenticated IPC client + projections
- `desktop/desktop_app.py` — real desktop GUI (Tk) + headless mode
- `desktop/acceptance_m0.py` — vertical-slice acceptance harness
- `tests/capt_runtime/test_desktop_m0.py` — 5 integration tests (real runtime)
- Docs: recovery, gap analysis, architecture, trust boundaries, contract map,
  ADRs, roadmap, M0 acceptance, verification report, evidence manifest,
  triple-recursion ledger.

Acceptance (proven): app launches; connects to real local CAPT runtime;
displays runtime/contract version + health; selects read-only demo mission;
displays MissionSpec, TaskGraph, DriverRun, capability scopes, event timeline,
evidence, verification result, ClaimGuard disposition; disconnect/reconnect
preserves state; no duplicate execution; tests + evidence exact-SHA-bound.

## Desktop M1 — Mission and execution observation  (NOT in this change)
- Create one bounded mission through a typed CAPT command (ADR-DT-005).
- Display TaskGraph + DriverRun streaming; capability grants/leases; Hermes vs
  reference driver selection; terminal evidence + ClaimGuard result.
- Requires: new governed command op + ADR + generated binding + conformance.

## Desktop M2 — Human approval and cancellation  (NOT in this change)
- Approval request display; signed/identified decision; cancellation;
  denied operation does not execute; restart preserves state.

## Desktop M3 — Evidence, replay, Project SEAL  (NOT in this change)
- Inspect evidence graph; export evidence bundle; replay from checkpoint;
  compare state digests; read-only Project SEAL case.

## Later milestones  (explicitly deferred)
Memory/ContextPack tooling, Knowledge Bubbles, plugin/skill management,
multimodal views, biosignal surfaces, packaging/signing/notarization,
cross-platform. Per the workflow stop rule, none are started here.

## Rollback criteria
- Any Critical/High finding in the trust boundary → freeze desktop merges and
  escalate. None were identified in the adversarial review (see
  TRIPLE_RECURSION_LEDGER).

## Tests per milestone
- M0: `tests/capt_runtime/test_desktop_m0.py` (5 tests, real runtime).
- M1+: add IPC command-contract tests + approval/denial behavior tests.
