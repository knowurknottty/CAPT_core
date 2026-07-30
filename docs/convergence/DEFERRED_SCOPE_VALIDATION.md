# DEFERRED_SCOPE_VALIDATION — evidence for or against OD-1 and OD-2

Generated: 2026-07-30. Objective: attempt to DISPROVE the recommendation to
defer Spaces (OD-1) and runtime adapters (OD-2) to v0.5.1. We state the
disproof attempt result explicitly.

## Attempt to disprove OD-1 (Spaces → v0.5.1)

Hypothesis to falsify: "Shipping v0.5 without first-class Spaces breaks an
approved v0.5 contract obligation."

Evidence examined:
- Treasure Chest doc 15 Workstream D lists Spaces as a workstream with
  deliverables. But doc 13 (Record Convergence) explicitly says "No new record
  unification work should delay v0.5 unless current duplication directly causes
  a release-blocking security, packaging, or correctness defect." Spaces are
  precisely such a unification/consolidation effort.
- SPACE_TRACEABILITY_MATRIX: 0/18 Space responsibilities implemented as a Space;
  13/18 have reusable building blocks in other abstractions; 4/18 genuinely
  absent (identity, ownership, CTP scope, policy inheritance). None of the 4
  absent items is referenced by any CURRENT public claim (PUBLIC_ARCHITECTURE_
  TRACEABILITY: 0 claims require Spaces).
- No public doc (README, PUBLIC_ARCHITECTURE, whitepaper, API manifest) asserts
  a Space as a shipped boundary. The word "Space" appears nowhere in current
  public claims.

Disproof result: **Cannot disprove OD-1.** Deferring Spaces removes no
functionality required by the approved v0.5 contract or any current public
claim. Spaces are a consolidation of existing per-subsystem boundaries
(lifecycle, namespace, project scope, proof scope, audit) plus 4 new primitives.
They improve architecture (reduce duplication, improve discoverability, enable
future multi-tenant capability) but unlock NO functionality that current
promises depend on.

## Attempt to disprove OD-2 (runtime adapters → v0.5.1)

Hypothesis to falsify: "Shipping v0.5 without an operational provider-neutral
runtime adapter contract breaks an approved v0.5 contract obligation."

Evidence examined:
- RUNTIME_CAPABILITY_MATRIX: architecture-level neutrality ACHIEVED and
  evidenced (core imports/operates without Hermes, offline, local-first; zero
  hermes imports; socket-deny import test passed today). Operational contract
  (adapter abstraction, provider/model selection, two-path proof) NOT achieved.
- PUBLIC_ARCHITECTURE_TRACEABILITY: the only adapter language is (a) architecture
  LAYER surfaces (CLI/CI/IDE/MCP/A2A/Hermes) — accurate as a layer; (b) explicit
  FUTURE (A15 "a future adapter may translate"); (c) seam-level (A16 search
  adapter seam). No present-tense claim of a shipped operational model adapter.
- The public claim "model-agnostic / no harness dependency" is TRUE at the
  architecture level and is evidenced. It does NOT assert an operational adapter
  layer.

Disproof result: **Cannot disprove OD-2.** Deferring the operational adapter
contract removes no functionality required by the approved v0.5 contract or any
current public claim. The contract is an operational consolidation that would
make the existing architecture-level neutrality PROVABLE via two paths; valuable
for v0.5.1 positioning, but not a prerequisite for truthful v0.5.0 claims.

## Negative-space review (mission Q5)

"If we ship v0.5 without Spaces and runtime adapters, what architectural promise
becomes false?" — answered with evidence:
- Promise "local-first, no cloud, no network on import": TRUE (proven). Not
  dependent on Spaces or adapters.
- Promise "model-agnostic, no harness dependency": TRUE at architecture level
  (proven). Not dependent on operational adapter contract.
- Promise "explicit governance/capability/proof/failure boundaries": TRUE
  (capability registry, governance, claimguard, proof engine). Not dependent on
  Spaces.
- Promise "auditable": TRUE (CTP append-only audit, evidence provenance). Space
  would add a Space filter view, not the audit itself.
- Promise "portable memory": TRUE (namespace + export/import). Space would
  bundle, not enable.
- **No promise becomes false.** Explicitly stated: shipping v0.5.0 without
  Spaces and without an operational runtime-adapter contract breaks ZERO current
  architectural promises. The only documentation-truth action needed is to keep
  adapter language at "architecture layer / future / seam" and not upgrade it to
  "shipped operational adapter" (already handled by claim ledger).

## Verdict
OD-1 and OD-2 are SUPPORTED by the evidence. The deferrals are genuine scope
management (consolidation of existing primitives + 4 new Space primitives +
operational adapter contract), NOT removal of contract-required functionality.
Both were RATIFIED by the owner on 2026-07-30 as written, with one documentation
caveat: tighten A16 "search adapters" to "search adapter seam" (enforced in
Package F / whitepaper recovery) to avoid any reader inferring a shipped
adapter. OD-4a (integration absorbs main) is now the actual release gate per
owner direction.
