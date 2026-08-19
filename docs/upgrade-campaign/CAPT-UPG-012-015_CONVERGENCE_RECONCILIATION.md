# CAPT-UPG-012–015 Convergence Reconciliation

Date: 2026-08-19

Integration branch: `integration/capt-core-main-convergence-r1`

CAPT provenance mission: `mission-main-convergence-7f16527a311c`

## Disposition

`IMPLEMENTED_ON_CURRENT_NATIVE_PROVIDER_SPINE`

This checkpoint restores four operator/support capabilities without creating a second authority plane:

- UPG-012 `.capt-flight` forensic reproducibility bundle;
- UPG-013 ContextPack component Merkle provenance probe;
- UPG-014 claim-scoped epistemic projection/TUI;
- UPG-015 live capability lease projection plus governed revoke/kill.

No release or main-merge authorization is implied.

## UPG-012 — `.capt-flight`

`capt_runtime.flight_recorder` exports deterministic content-addressed forensic/support archives over authoritative EventStore observations.

The bundle is explicitly classified `forensic_projection_only` and cannot:

- mutate EventStore state;
- authorize replay;
- create verification;
- create ClaimGuard disposition;
- dispatch a model/tool;
- grant capability authority.

The exporter recursively redacts configured secret-bearing fields and explicit secret values before archive creation. Manifest/member digests are independently verified; missing, modified, or unmanifested members fail closed.

## UPG-013 — ContextPack Merkle provenance

`capt_runtime.context_merkle` provides deterministic component identities and localized invalidation for ContextPack analysis.

It preserves the existing canonical `contextPackDigest` as authoritative contract identity. The Merkle root is provenance/invalidation metadata only.

The separate prompt-prefix plan hashes exact serialized prefix text and explicitly sets `providerCacheHitClaim=false`; prefix identity is not represented as proof that any provider cache was actually hit.

## UPG-014 — claim-scoped epistemic ladder

The shared Dashboard now carries:

- authoritative claims;
- `verifications_by_claim`;
- a claim-scoped `epistemic_ladder` projection.

Verification, contradiction, observation, inference, staleness, ClaimGuard promotion state, and advisory-vs-committed provenance remain distinct.

When multiple claims have verification records, the old compatibility `verification` field becomes an explicit `claim_scoped` marker rather than inventing one global certainty/verdict.

Claim acceptance remains separate from universal truth by contract.

`capt-tui` now points to the lease-aware TUI, which extends the epistemic surface rather than replacing it.

## UPG-015 — capability lease inspector and kill key

The lease inspector is projection-only. It exposes current grant/lease scope, validity window, effective use ceiling, consumption, open reservations, reconciliation-required reservations, and revocation state without mutating authority.

`revoke_capability` is added to the authenticated operator command surface. The relay delegates to the existing canonical `RuntimeService.revoke()` transition.

### Canonical target-binding repair

Revocation target binding is enforced in `RuntimeService.revoke()` itself, not trusted to the UI/relay:

- `targetKind=grant` requires `targetId == grantId`;
- `targetKind=lease` requires an existing lease and `targetId == active leaseId`.

A semantically mismatched target fails with an authority violation before EventStore mutation. This protects direct callers as well as GUI/TUI/MCP relays.

The command surface preserves the current prompt-approval and Cohort steering paths by stacking `LeaseRuntimeCommandService` over the steering-aware governed command service.

Exact retry is idempotent; same-key/different-semantic replay fails closed. Wrong authenticated operator/session cannot revoke. Revocation survives process close/reopen and immediately causes subsequent lease checks to fail.

## RED → GREEN evidence

Before implementation, the focused tranche failed collection because the current native/provider spine lacked:

- `capt_runtime.flight_recorder`;
- `capt_runtime.context_merkle`;
- `capt_ui.operator.epistemics`;
- `capt_ui.operator.leases`.

After integration, the discriminating tranche passed `22/22`, including direct canonical RuntimeService revocation-target mismatch rejection.

## Broad verification

- Python repository: `1019 passed, 13 skipped, 12 deselected`;
- generated contract drift: `DRIFT CHECK: OK (11 generated files match the schema source)`;
- TypeScript fixture parity: PASS;
- epistemic + lease TUI imports: PASS;
- Swift package: `54 executed, 4 explicit live-runtime skips, 0 failures`;
- `swift build --product CAPTNativeMac`: PASS;
- `git diff --check`: PASS.

## Remaining limits

The flight recorder and Merkle probe are support/provenance tools, not proof of runtime correctness. The epistemic ladder is presentation only. The lease inspector is projection only; only RuntimeService transitions alter authority.

Installed-wheel/app and real macOS↔RuntimeService↔MCP cross-surface acceptance remain terminal convergence gates.
