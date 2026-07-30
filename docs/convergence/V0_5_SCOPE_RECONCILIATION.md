# V0_5_SCOPE_RECONCILIATION — formal resolution

Generated: 2026-07-30. This document resolves the conflict between the earlier
archaeology conclusion ("no blocking implementation gap for the six-pillar
public architecture") and the Finish-Line Playbook's larger workstream list.

## 1. The two positions, stated precisely

**Position N (narrow):** The six-pillar public architecture (ADR-0008) is
implemented, tested (715 passing today), packaged (wheel/sdist built and
clean-installed today), and validator-clean (`--final` 12/12 today). No
implementation gap blocks THAT surface.

**Position W (wide):** Playbook doc 15 §1 says "the approved feature set is
sufficient" BUT lists as remaining: integrating preserved branches, completing
Spaces, proving provider-neutral operation, validating public claims, closing
documentation/trust/security/packaging/release-evidence gaps.

## 2. Why the difference exists — determination

Examined causes, with findings:

1. **Changed owner-approved scope?** NO changed contract exists in writing.
   The Treasure Chest is the latest written v0.5 contract. Owner live
   instructions during archaeology restricted ACTIVITY ("do not implement"),
   not SCOPE. Position N was an activity-scoped conclusion misread as a
   scope conclusion.
2. **Public architecture narrower than Playbook?** YES — this is the primary
   cause. ADR-0008's six pillars deliberately exclude Spaces and runtime
   adapters. Doc 15 workstreams D/E sit ABOVE the pillar contract. Both
   documents are internally consistent; they answer different questions
   ("what is the stable public API" vs "what must v0.5 ship").
3. **Spaces/adapters existing under other names?** PARTIALLY, seams only.
   Memory `namespace` (per-record), `ProjectWorkspace`/`WorkspaceScope`
   (evidence isolation), `ResearchAdapterRegistry` (registry pattern
   precedent). None is the required cross-subsystem boundary or model-runtime
   contract. Evidence: SPACE_READINESS_REVIEW.md, RUNTIME_ADAPTER_READINESS_REVIEW.md.
4. **Treasure Chest aspirational?** Partially — doc 15 itself marks the
   whitepaper (H) as post-stabilization and doc 13 defers record convergence.
   But D/E/F/G/I are written as required workstreams with named deliverables.
5. **Positioning vs package correctness?** Splits cleanly:
   - Package correctness needs: F-subset (security campaign), G (doc truth),
     I (completeness audit), doc 07 evidence files.
   - Product positioning needs: D (Spaces), E (adapters), F-full (Trust
     Center + standards mappings).
6. **v0.5.0 vs v0.5.1?** This is the real decision surface. See §4.

## 3. Per-capability ruling

| Capability | In approved v0.5 contract (doc 15)? | Required for truthful public claims? | Required for release mechanics? | Deferral changes messaging? | Owner decision needed? |
|---|---|---|---|---|---|
| Spaces (D) | YES as written | NO — no current public claim asserts Spaces | NO | YES — whitepaper/positioning must not mention Spaces as present; "isolation boundary" language must stay project-scoped | YES (OD-1) |
| Runtime adapters (E) | YES as written | NO — current claim is "model-agnostic/harness-independent," which IS true at the architecture level (zero hermes imports, proven today); adapters would make it OPERATIONALLY proven | NO | YES — without E, avoid "provider-neutral runtime" as a shipped feature; keep "no architectural dependency on any harness" | YES (OD-2) |
| Security campaign (doc 04) | YES | YES — "secure, auditable" claims need a scan of record | YES (doc 07 requires security closure) | NO | NO — required either way |
| Trust Center + mappings (F) | YES | Partially — threat model + SECURITY.md are baseline; ISO/SOC2 mappings are positioning | Mappings: NO; threat model/disclosure: YES per doc 07/08 phase 1 | Mappings deferral: minor | Split: baseline required, mappings OD-3 |
| Doc truth + claim ledger (G) | YES | YES | YES | NO | NO |
| Completeness audit + FINAL_RELEASE_BLOCKERS (I) | YES | YES | YES | NO | NO |
| Exact-SHA evidence files (doc 07) | YES | YES | YES — machine-enforced failure conditions | NO | NO |
| Whitepaper refresh (H) | YES, post-stabilization | YES if whitepaper ships with v0.5 | NO | YES | NO (sequenced last) |
| Branch integration (main↔integration) | YES (Workstream B) | YES — public main currently does NOT contain v0.5; releasing requires convergence | YES | YES | YES (OD-4: direction of merge) |

## 4. RECOMMENDED RESOLUTION (for owner ratification)

Split doc 15 into two release trains:

**v0.5.0 — "verification substrate, evidenced":**
- Convergence of main + integration (Workstream B; the new blocking item found
  in this pass).
- Security campaign at the final candidate SHA (doc 04 deterministic pass +
  prioritized manual scopes).
- SECURITY.md + THREAT_MODEL.md + privacy/data-handling doc (doc 08 Phase 1).
- SBOM (trivial: pyyaml only) + supply-chain statement.
- Documentation truth: fix UNFROZEN contradiction, claim ledger, terminology.
- Doc 07 evidence files, sealed at the frozen SHA.
- Harsh-reviewer gate (doc 16).
- NO Spaces, NO runtime adapters, NO ISO/SOC2 mappings.
- Public language: never claims Spaces/adapters; says "model-agnostic
  architecture; no harness dependency; local-first" — all evidenced today.

**v0.5.1 (or v0.6) — "governed multi-runtime":**
- Workstream D (Spaces) — with migration design from SPACE_READINESS_REVIEW.
- Workstream E (adapters, two proven paths).
- Trust Center full build-out + standards mappings.
- Whitepaper major revision (Spaces + adapter contract + portability scenario).

Rationale: D and E are the two largest engineering efforts in the playbook,
both carry schema/API stability risk, and NEITHER is needed to make current
public claims true. Deferring them shortens the path to a truthful, evidenced
v0.5.0 while the claims ledger keeps the public surface honest. This maximizes
long-term credibility (owner's optimization criterion of record).

## 5. What this resolution does NOT decide

- OD-1/OD-2: whether owner accepts moving D/E out of v0.5.0 (this document
  recommends; owner ratifies).
- OD-4: merge direction for main↔integration convergence (options in
  IMPLEMENTATION_WORK_PACKAGES.md, Package C).
- Whether v0.5.0 publishes to a package registry or remains GitHub-only.

No implementation begins until OD-1, OD-2, OD-4 are answered.
