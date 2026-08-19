# CAPT-UPG-017–019 Convergence Reconciliation

Date: 2026-08-19

Integration branch: `integration/capt-core-main-convergence-r1`

CAPT provenance mission: `mission-main-convergence-7f16527a311c`

## Disposition

`IMPLEMENTED_ON_CURRENT_NATIVE_PROVIDER_SPINE_AS_PROJECTION_SURFACES`

No new mutation authority is introduced by these surfaces. No release or main-merge authorization is implied.

## UPG-017 — Provenance DAG / Lens

The shared read projection now exposes already-authoritative aggregate families required to render provenance:

- capabilities / leases;
- artifact promotions;
- durable Cohorts;
- replay forks;
- existing missions/tasks/approvals/DriverRuns/claims/verifications/events.

`build_provenance_graph()` creates deterministic nodes and typed edges only from explicit durable identifiers and relationships. Missing relationships remain unknown rather than being guessed.

The graph:

- detects contradictory enrichment for the same node identity;
- detects cycles rather than rendering a false DAG;
- keeps approval request and human decision distinct;
- keeps evidence, verification, ClaimGuard decision, and artifact-promotion authority distinct;
- models grant and lease separately;
- models historical replay source -> replay fork -> new mission without implying historical authority reactivation;
- includes provider/model/prompt provenance only when explicitly present.

`authority=projection_only` is hard-coded in graph output. `capt-provenance` is a packaged headless/Tk read surface.

## UPG-018 — Cohort Deliberation Chamber

The Chamber is a deterministic read projection over the hardened durable Cohort state integrated in UPG-010/011.

It distinguishes:

- stale-epoch contributions;
- prior-round/current-epoch contributions;
- current-round contributions;
- impossible/future-round anomalies.

Only current-round PASS from all required participants can satisfy projected silence quorum. Current-epoch material dissent, escalation, or evidence-request debt blocks projected quorum. Recorded authoritative stopping state is preserved separately from display-side recomputation; disagreement produces an integrity warning rather than silently rewriting history.

The projection does not invent proposal text, provider/model identity, or confidence scores that the durable Cohort contract does not contain. Its semantics explicitly state that quorum is not a truth claim.

`capt-cohort` and `capt-cohort-tui` are projection/control surfaces. Their only mutation capability reuses the already-governed human `steer_deliberation` command; the Chamber itself cannot admit contributions or change authority.

## UPG-019 — Security Closure Cockpit

The Security Cockpit projects the existing fail-closed SecurityGate result. It does not run controls, authorize release, or produce a universal security verdict.

Projection hardening preserves:

- PASS / FAIL / NOT_VERIFIED / N/A distinctions;
- exact source SHA;
- evidence references;
- stale-vs-missing evidence;
- per-control severity and release-blocking state;
- current blockers.

A claimed PASS without a source SHA or evidence reference is downgraded to NOT_VERIFIED in the cockpit. Projection-created blockers force an inconsistent upstream PASS decision back to BLOCKED. N/A is never converted to PASS.

The output permanently sets:

- `releaseAuthorized=false`;
- `globalSecurityVerdict=null`;
- `authority=projection_only`.

### Current corrected Core baseline

The cockpit was tested against the converged 47-control Core catalog and empty exact-head evidence baseline:

- PASS: 0
- FAIL: 0
- NOT_VERIFIED: 21
- N/A: 26
- gate: `BLOCKED`

`CAPT-SUP-07 — Set billing caps and alerts on every paid service` is present and remains a blocker. The projection therefore does not regress to the historical UPG-019 46-control catalog.

## RED -> GREEN evidence

Before implementation, the tranche failed collection because the current native/provider spine lacked:

- `capt_ui.operator.provenance`;
- `desktop.provenance_lens`;
- `capt_ui.operator.security_cockpit`;
- related Chamber/Lens surfaces.

After integration:

- focused Provenance/Chamber/Security projection gate: `28 passed`;
- current 47-control Security Cockpit regression: PASS;
- projection/TUI/desktop imports: PASS.

## Broad verification

- Python repository: `1060 passed, 13 skipped, 12 deselected`;
- generated contract drift: `DRIFT CHECK: OK (11 generated files match the schema source)`;
- TypeScript fixture parity: PASS;
- Swift package: `54 executed, 4 explicit live-runtime skips, 0 failures`;
- `swift build --product CAPTNativeMac`: PASS;
- `git diff --check`: PASS.

## Authority boundary

These are read/projection surfaces. Provenance is not verification, Cohort quorum is not truth, and a security gate/cockpit PASS—if eventually achieved—would remain a bounded release-control result rather than a universal claim that CAPT is secure.
