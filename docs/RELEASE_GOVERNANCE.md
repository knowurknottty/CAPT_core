# RELEASE_GOVERNANCE.md — Public/Private Release-Boundary Review

> **Purpose:** prepare the public/private release-boundary decision for owner
> review. This document *classifies* and *recommends*; it does **not** change
> `architecture/registry.yaml`. Changing the registry's `public_release_target`
> is an owner [B] decision (see `AGENTS.md` owner gates).
>
> **Evidence base:** `architecture/registry.yaml` (every subsystem carries a
> `public_release_target` and `implementation_status`). All classifications below
> are derived from that machine-readable registry, not invented here.

## Classification scheme

| Class | Meaning | Ships in `capt-solo` wheel? |
|-------|---------|------------------------------|
| PUBLIC | Core, supported, in the public wheel | Yes |
| RESEARCH | Experimental/biological-analogy research; external repo | No (registry: `research_package`) |
| EXTERNAL | Separate distributable package | No (registry: `external_package`) |
| OPTIONAL | Opt-in plugin/package, degrades independently | No (registry: `optional_plugin`) |
| OWNER REVIEW | Boundary needs owner sign-off before public release | Per owner decision |
| DEPRECATED | Retired | n/a (none in registry) |

## PUBLIC — ships in `capt-solo` (CAPT_core)

All `public_release_target: CAPT_core` subsystems that are `implementation_status: complete` or `partial` and live in this repo. Verified present in tree (no research modules found under `capt_solo/`):

- Identity (CAPT-IDN, partial), Ontology (CAPT-ONT, spec-only — doc only), Constitution (CAPT-CON, spec-only — doc only), Reasoning Core (CAPT-REA, partial), MemoryEngine (CAPT-MEM, complete), CSG (CAPT-CSG, complete), Episodic/ECHO (CAPT-EPI, partial), Semantic (CAPT-SEM, complete), Procedural (CAPT-PRO, complete), Prospective (CAPT-PRS, complete), Context Builder (CAPT-CTX, complete), Search/Retrieval (CAPT-SCH, complete), Deduplicate (CAPT-DDUP, complete), Normalize (CAPT-NORM, complete), Memory Compression/AntiToken (CAPT-ATOK, complete), Retrieval Feedback (CAPT-RFA, complete), Replay (CAPT-RPLY, spec-only), TTL/Retention (CAPT-TTL, complete), Temporal Ordering (CAPT-TEMP, complete), Export/Import (CAPT-EXIM, complete), Migration (CAPT-MIG, complete), HMC/ENGRAM/DREAM (CAPT-HMC/ENG/DRM — **Research maturity but `public_release_target: CAPT_core`**; `implementation_status: missing`, external repo), Autobiographical (CAPT-AUTO, missing), Hermes Plugin Interface (CAPT-HERM, complete), Foundry/Governance/Proof (core), KHSB, CTP.

**Note on HMC/ENGRAM/DREAM:** the registry marks them `Research` maturity yet `public_release_target: CAPT_core`, with `implementation_status: missing` (no code in this tree). This is an internal registry inconsistency (maturity vs target). **Recommendation:** owner should either (a) reclassify their `public_release_target` to `research_package`, or (b) confirm they are intentionally documented-but-not-shipped core stubs. Flagged as OWNER REVIEW (canon/registry drift, P2).

## RESEARCH — `research_package` (do NOT ship in public wheel)

Registry entries, all `implementation_status: missing`, all in `biocapt-ecosystem` (not in this repo):

- CONS (CAPT-CONS, Global Workspace, ADR-0003)
- QIPC (CAPT-QIPC, Quantum-Inspired Consensus, ADR-0001)
- NEDA (CAPT-NEDA, Neural Event-Driven, ADR-0003, DISABLED in source)
- FILT (CAPT-FILT, Attentional Filter, ADR-0003, **DISABLED in source**)
- FSR (CAPT-FSR, Feedback Regulator, ADR-0003, **DISABLED in source**)
- OUROBOROS (CAPT-OUROBOROS, Self-referential learning, ADR-0003)

**Recommendation:** keep `research_package`. None are in the `capt-solo` tree, so the public wheel already excludes them. Owner [B] gate: confirm these remain out of the public distribution and are documented as external research.

## EXTERNAL — `external_package` (separate distribution)

- RYS Bridge (CAPT-RYS, recursive yield bridge to CAPT-RYS; `network_behavior: external (gated)`, ADR-0005). `implementation_status: missing`.
- CAPTLANG (CAPT-CAPT, dialect→WASM compiler; `biocapt-ecosystem-fullcaptlang`). `implementation_status: missing`.

**Recommendation:** keep `external_package`. Safe abstract contracts only; no network call unless explicitly enabled (ADR-0005, I-01/I-09). Owner [B]+[S] gate: confirm no network gateway ships enabled by default.

## OPTIONAL — `optional_plugin`

- PULSE (CAPT-PULSE, `optional_plugin`, `implementation_status: missing`, `network_behavior: external (gated)`).

**Recommendation:** keep `optional_plugin`. Degrades independently; not in core. Owner [B]+[S] gate: privacy/security review of any network transport before it is published as an optional plugin.

## OWNER REVIEW items (require owner, not steward)

1. **[B] Research boundary:** confirm FILT/FSR/NEDA/CONS/QIPC/OUROBOROS stay `research_package` and out of the public wheel. (Evidence: none present in tree; registry already tags them. Low risk, but it is a boundary decision.)
2. **[B] HMC/ENGRAM/DREAM target:** resolve the maturity(`Research`)/target(`CAPT_core`) inconsistency in the registry. Either reclassify to `research_package` or confirm intentional doc-only core stubs.
3. **[S] Privacy review:** Consent (CAPT-CONS-related) and Sync transports — privacy review at integration before public release.
4. **[B]+[S] PULSE/RYS:** network gateways — confirm disabled-by-default and privacy-reviewed before any optional/external publication.

## What this session did NOT do

- Did **not** modify `architecture/registry.yaml` (that is an owner [B] decision).
- Did **not** delete, relocate, or rename any subsystem.
- Did **not** add or remove modules from the public wheel (none behind a boundary are present in the tree).

## Verification

- `grep public_release_target` over `architecture/registry.yaml` → 10 entries tagged `research_package`/`external_package`/`optional_plugin` (lines 234,259,284,335,1489,1757,1782,1833,1858,1909). All `implementation_status: missing`.
- `find capt_solo -type d` for reasoning/cig/hdr/meta/neda/consc/qipc/ouroboros/filt/fsr → **empty** (no research code in tree).
- `capt workspace validate` → 0 fail (workspace remains internally consistent after this review doc added).
