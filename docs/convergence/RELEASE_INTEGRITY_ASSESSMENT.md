# RELEASE_INTEGRITY_ASSESSMENT — v0.5 / v0.5.1 split soundness

Generated: 2026-07-30. Independent assessment of the proposed split.

## Proposed split
v0.5.0: verification substrate · evidence · governance · documentation truth ·
release evidence · security campaign.
v0.5.1: Spaces · runtime adapters · expanded standards work.

## 1. Internally consistent?
YES. The v0.5.0 functional set has previously passed the recorded test,
packaging, and validator gates; final clearance remains pending repository
convergence (OD-4) and exact-SHA revalidation. The v0.5.1 set is exactly the
functionality proven ABSENT or partial in SPACE_TRACEABILITY_MATRIX /
RUNTIME_CAPABILITY_MATRIX. No item sits ambiguously across the boundary that
would create a half-shipped feature. The one coupling (adapter policy selection
needs Spaces) is resolved by ordering D before E in v0.5.1 — internally coherent.

## 2. Externally truthful?
YES. PUBLIC_ARCHITECTURE_TRACEABILITY shows every CURRENT public claim is
satisfied by the v0.5.0 set alone. The split does not require retracting any
true claim; it only requires NOT asserting Spaces/adapters as present (already
enforced by PUBLIC_CLAIM_LEDGER). The "model-agnostic" claim remains true
(architecture-level, evidenced). No external promise is broken.

## 3. Architecturally coherent?
YES. v0.5.0 ships a coherent local-first verification substrate with explicit
boundaries (capability/proof/governance/claimguard). v0.5.1 layers governance
isolation (Spaces) and operational provider-neutrality (adapters) ON TOP without
disturbing the v0.5.0 core — both are additive (nullable space_id on receipts;
new adapters package; no signature changes to existing stable APIs). Coherent
because the deferrals are extensions, not retrofits.

## 4. Maintainable?
YES, with one caveat. The current main↔integration divergence (29 vs 66
disjoint commits) MUST be resolved first (OD-4 / Package C) — otherwise
maintaining two histories is unmaintainable. Once integration absorbs main and
becomes the single release branch (OD-4a), the v0.5.0/v0.5.1 split is a normal
minor-version roadmap, maintainable via the existing ADR + validator gate
discipline. Caveat: do NOT start v0.5.1 work on a separate long-lived branch
that diverges again; use the same release branch with feature flags / provisional
API tiers (already the pattern: Provisional stability tier exists).

## 5. Technically defensible?
YES. The deferral is defensible because:
- Evidence proves the deferred items are consolidation, not missing core
  function (DEFERRED_SCOPE_VALIDATION).
- The security campaign (v0.5.0) is the highest-risk item for the "secure"
  public claim and is INDEPENDENT of Spaces/adapters — shipping it sooner
  reduces risk exposure.
- The deferred items carry schema/API stability risk (Space identity, CTP
  space_id, adapter contract) that is prudent to keep out of the first public
  release.
- The Treasure Chest itself (doc 13) authorizes deferring unification work that
  does not cause a release-blocking defect — and none of the deferred items
  causes such a defect (verified).

## Independent risks noted (not blockers)
- R1: If owner later wants Spaces in v0.5.0, the migration (default-Space
  adoption of existing state) must be backup-gated and tested on real user
  state. Documented in SPACE_READINESS_REVIEW §5.
- R2: The operational adapter contract's two-path proof requires Spaces (policy
  selection) — so E cannot be fully PROVEN before D. Sequencing D→E in v0.5.1 is
  correct; claiming adapter neutrality before D would be unprovable. Keep
  "architecture-level neutrality" language only until E ships.
- R3: `verify_runtime.py` is absent at HEAD (only on main) — the doc-07 command
  `python3 verify_runtime.py` cannot run on the integration candidate until
  Package C recovers it. This is a documentation-truth gap, not a scope gap.

## Verdict
The split is internally consistent, externally truthful, architecturally
coherent, maintainable (post-OD-4), and technically defensible. Recommended for
ratification. The only precondition is OD-4 (converge main→integration) which is
orthogonal to OD-1/OD-2 but required before any freeze.
