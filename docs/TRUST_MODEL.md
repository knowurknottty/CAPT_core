# TRUST_MODEL — CAPT Core Trust, Provenance & Evidence

Status: RECOVERED (knowledge archaeology pass, 2026-07-30)
Sources: `docs/EVIDENCE_MODEL.md`, `docs/VSI_MODEL.md`, `docs/PROOF_ENGINE.md`,
`docs/GOVERNANCE.md`, `docs/CLAIMGUARD.md`, `docs/SECURITY.md`, ADR-0006/0009/0011.

## Trust is earned, scoped, and explicit
CAPT does not have implicit global trust. Every trust assertion is scoped
(project-local by default), timestamped, and provenance-tagged.

## The evidence continuum (distinct concepts, never collapsed)
From `docs/EVIDENCE_MODEL.md`:
| Concept | Meaning | Where |
|----------|---------|-------|
| present | observed/recorded right now | `EvidenceSource` |
| believed | asserted by authority, not yet verified | `EvidenceRecord(USER_DECISION)` |
| inferred | derived; quarantined until corroborated | `DERIVED_INFERENCE`/`SIMULATION_RESULT` |
| attempted | an action was tried, outcome pending | `SelfModificationRecord` |
| changed | a concrete mutation occurred | `InvalidationEvent.changed_paths` |
| verified | a verification run passed at a known state | `EvidenceStatus.CURRENT` + VSI |
| valid | CURRENT and no active invalidation | — |
| invalidated | proof no longer applies due to an event | `EvidenceStatus.INVALIDATED` |

## Provenance tracking
- Every evidence object carries: `type`, `source`, `hash`, `trust` (0.0–1.0),
  `scope`, `created_at`, `expires_at`.
- Evidence older than `DEFAULT_EVIDENCE_TTL` (90 days) is stale unless renewed.
- ADR-0009: canonical evidence ownership — one authority per scope.

## State-bound verification (VSI)
- Verification attaches to the STATE, not the conversation age (VSI_MODEL).
- `VerifiedStateIdentity`: repo, project, branch, HEAD, scoped file hashes,
  dependency state, runtime identity, env, command, scope.
- Two VSIs equivalent iff all fields (except timestamp) match. Untracked
  artifacts excluded from equivalence.
- Implemented: `capt_solo/verification/identity.py` (SHIPPED in v0.5).

## Proof Engine (epistemic backbone)
- Aggregates evidence against declared `ProofRequirement`s.
- `ProofAggregate.satisfied` = all requirements have sufficient in-scope,
  sufficiently-trusted, non-stale evidence.
- Implemented as `capt_solo/foundry/proof.py` (Proof Engine = Foundry Proof).
  Status: SHIPPED (partial — aggregation present; ledger separate).

## ClaimGuard (claim discipline)
- Scans text for claim-trigger verbs (complete, fixed, verified, secure, ...).
- Downgrades unsupported claims with explicit, scoped language. Never reports
  unverified as verified.
- Degradation-aware: a capability degraded only on `macos` is reported as such,
  not globally revoked.
- Status: CONCEPTUAL — no module in baseline. Documented intent; candidate for
  v0.5.1 or research.

## Governance (audited mutation)
- Every consequential action wrapped in a CTP transaction + `GovernanceReceipt`.
- `Governance._act(action, actor, target, reason, fn)`: named actor required,
  CTP tx begun, fn run, tx committed, receipt recorded; abort on failure.
- Status: CONCEPTUAL — `governance` module absent in baseline. The CTP journal
  (capt_solo.ctp) provides the transactional substrate; the Governance wrapper
  layer is not implemented.

## Trust boundaries
- Local-first: no remote persistence without explicit consent (CAPT_CANON).
- Secrets screening: `memory/secrets.py` screens before persistence.
- AntiToken: `memory/antitoken.py` reduces token surface, preserves structure.
- ATE component (cherry-pick candidate): external MCP token handling, secret-clean.

## Failure semantics
- Degradation-aware language (ClaimGuard concept) is the trust model's output
  contract: never falsely assert "verified".
- Release gates fail closed (ADR-0006, validator `sha_match`/`clean_tree`).

## Missing / deferred trust pieces
- Proof Ledger (explicit immutable ledger) — registry lists it; not in code.
- IMMU (immutable log) — registry; not in code.
- Autobiographical memory trust — missing.
- These are flagged for owner decision (PORT-or-exclude per matrix line 128).
