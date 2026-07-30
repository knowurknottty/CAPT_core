# RELEASE_BACKLOG — CAPT Core v0.5 (intentionally deferred)

Generated: 2026-07-30
Items here are NOT in v0.5 scope. They are preserved for future work. No deletion.

## Deferred subsystems / capabilities (no module found in baseline)
These were named in the architecture review but have no implementation in the
v0.5 tree. Either conceptual, renamed, or out of scope. Flagged for owner review
(Phase 7 evidence gap) — not removed.
- ClaimGuard — no module; possible conceptual/renamed.
- Knowledge Bubble Runtime — no module; possible conceptual.
- Governance — no module; possible cross-cutting concern, not isolated.
- Messaging — no module; possible external (Hermes) dependency.
- Migration — no dedicated migration module; schema identity checks exist instead.

## Deferred branch content (archived, not merged)
- `codex/capt-v0.5-p0-release-hardening` — looped incident lineage; superseded.
- `codex/cve-v0.2-operational-continuity` — docs already in baseline.
- `preservation/hy3-sha-loop-20260730-124704` — incident safety branch.
- `main` (v0.4) — historical root, fully contained in baseline.
- `integration/full-public-architecture` — Evidence Engine, already absorbed.

## Deferred engineering work
- Engines / Ontology dedicated test coverage (Batch 3, post-v0.5 acceptable).
- KHSB / Foundry / CTP documentation pages (Batch 2, low risk, can slip).
- MCP adapter unification: baseline lacks MCP; ATE branch has it. Decision deferred
  to owner (merge via Batch 1 or treat as v0.5.1).
- Public Trust Center, Security Boundaries, Privacy, Compliance, Threat Model
  publication — explicitly out of v0.5 scope per release discipline.

## Deferred process
- Tagging v0.5, merging to main, publishing — blocked until owner declares GA.
- Branch integration beyond Batch 1–3 — not authorized in this phase.

## Known risks carried into v0.5
- CTP journal runtime in baseline may diverge from ATE-branch fixes; Batch 1
  reconciles. If Batch 1 is deferred, CTP journal contract is unverified against
  the hardened lineage.
- `engines`, `ontology` ship without dedicated tests (experimental/internal).
