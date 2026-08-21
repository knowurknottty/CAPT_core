# CAPT-UPG-001–005 Convergence Reconciliation

Date: 2026-08-19

Integration branch: `integration/capt-core-main-convergence-r1`

Integration base: `5ec276e891cf9fbfff2ce619a742f4b0f210c1ee` (`fix/local-openai-compatible-provider-r1`, PR #107 head)

CAPT provenance mission: `mission-main-convergence-7f16527a311c`

## Disposition

`IMPLEMENTED_ON_CURRENT_NATIVE_PROVIDER_SPINE_WITH_CORRECTIONS`

This is an integration checkpoint, not release authorization. The security gate remains fail-closed until every applicable control has exact-head evidence.

## Reconciled source lineage

The useful semantics from these historical upgrade commits were transplanted onto the current PR #107 lineage rather than merging their stale branch ancestry:

- CAPT-UPG-001 — `cf65e8136d50e6bee818fbed9422008d6e778d7c` — bounded production IPC framing.
- CAPT-UPG-002 — `6689353b2181617f05f09c02b1afe15832bfeb73` — persistent SQLite file-permission hardening.
- CAPT-UPG-003 — `6785e97cde2c3bfa68d5633164a6df6ab7f56b30` — durable security-rejection audit trail.
- CAPT-UPG-004 — `aa0e9ee91a6be0a2966222c4f8093f3a554fb165` — provider request/token/output/cost-governor foundation.
- CAPT-UPG-005 — `cc91836c29a59cabe81a030356ac56960e967bce` — prompt/model injection assurance tests.

The PR #49 security-gate/evidence modules that these upgrades depended on were also restored from the verified UPG-019 terminal lineage.

## Corrections made during convergence

### 1. Resource ceilings no longer reset for every ProviderDriver

The historical UPG-004 implementation created a new `TokenCostGovernor` inside each fresh `ProviderDriver`. The current RuntimeService creates fresh provider drivers for governed runs, so that design reset supposed per-session counters after each run.

The converged implementation instead creates one governor per authenticated RuntimeService session and passes that same governor into every provider driver created for the session. Regression coverage proves a second fresh driver cannot bypass a one-request session ceiling and that budget rejection occurs before any network request.

Provider requests now also carry a concrete per-request output cap:

- OpenAI-compatible: `max_tokens`.
- Ollama native generate: `options.num_predict`.

Provider-reported token usage is reconciled when available; otherwise bounded estimates are recorded. Provider-reported cost is recorded when available. This internal cost accounting is not represented as proof of an external provider-side billing cap.

### 2. Security rejection IDs are immutable

Historical UPG-003 used `INSERT OR REPLACE`, allowing the same rejection ID to overwrite an earlier audit record. The converged implementation uses immutable insert semantics; duplicate IDs fail rather than rewriting history.

The inherited audit test also had an ordering-sensitive `or` expression that could raise `KeyError` for a valid reverse row order. The test was corrected to assert the intended order-independent property.

### 3. Missing paid-service control restored

The historical high-assurance R2 document explicitly required a machine-visible billing-cap/alert control and recommended `CAPT-SUP-07`, but the terminal UPG-019 catalog still contained only 46 controls and never added it.

The converged catalog contains 47 controls and adds:

`CAPT-SUP-07 — Set billing caps and alerts on every paid service`

Because CAPT ships optional paid cloud-provider capability, the Core profile exposes `paid_service`, making this control applicable rather than silently N/A.

Current empty-baseline gate result is therefore intentionally:

- PASS: 0
- FAIL: 0
- NOT_VERIFIED: 21
- NOT_APPLICABLE: 26
- decision: `BLOCKED`

`CAPT-SUP-07` is one of the blockers until real provider-side billing-cap and independent alert evidence exists.

## Preserved PR #107 invariants

The transplant preserves the current provider/native spine rather than reverting to old provider behavior:

- exact approved dispatch-prompt digest binding remains enforced;
- local OpenAI-compatible endpoint classification remains endpoint-derived;
- credentialless provider execution remains restricted to admitted local loopback endpoints;
- provider output remains untrusted / awaiting independent verification;
- native provider prewarm and New Chat global-default behavior remain intact;
- bounded IPC remains the same four-byte big-endian framed JSON protocol used by the native Swift client.

## Verification at this checkpoint

Focused security/provider/runtime slice:

`75 passed`

Full Python repository suite:

`961 passed, 13 skipped, 12 deselected`

Contract generation drift:

`DRIFT CHECK: OK (11 generated files match the schema source)`

Swift package:

`54 executed, 4 explicitly opt-in live-runtime tests skipped, 0 failures`

Native build:

`swift build --product CAPTNativeMac` — PASS

Repository whitespace check:

`git diff --check` — PASS

## Deliberately unresolved release blockers

1. **EventStore / MemoryStore content encryption is not proven.** `0o600/0o700` permission hardening is not at-rest encryption. `VIBE1-05` must remain unverified until real sensitive-state encryption semantics and migration/recovery evidence exist.
2. **Provider-side paid-service billing caps/alerts are not proven.** Internal token/request/output/cost accounting does not substitute for a hard external billing cap and independent alert configuration. `CAPT-SUP-07` remains unverified.
3. **Exact-head security evidence is not yet complete.** The empty committed profile is deliberately fail-closed; no current release PASS is claimed.

These blockers do not invalidate this integration checkpoint. They prevent a release-security PASS until separately closed with exact evidence.
