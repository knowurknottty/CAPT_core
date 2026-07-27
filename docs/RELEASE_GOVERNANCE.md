# RELEASE_GOVERNANCE.md — Public/Private Release-Boundary (OWNER DECIDED)

> **Status:** owner decisions applied (session 2026-07-27). This document is now
> the **canonical boundary record**. `architecture/registry.yaml` is the
> machine-readable companion; other files reference this.
>
> **Evidence base:** `architecture/registry.yaml` (every subsystem carries
> `public_release_target` + `implementation_status`) and direct forensic inspection
> of `capt_solo/` (no RYS/Puter/mesh/private code present in tree).

## Owner Decisions (authoritative)

- **D1 — Research modules may be public if real.** FILT, FSR, NEDA, CONS, QIPC,
  OUROBOROS are approved for public release **where actually implemented, safe,
  accurately described, and tested**. None of these have code in the `capt-solo`
  tree (verified: `find` for their dirs is empty; registry `implementation_status:
  missing`). They therefore remain **publicly documented specifications**
  (`research_package`), not shipped code. A missing module may be documented as
  experimental/planned but **must not** be presented as functioning production
  capability. Truthfulness is mandatory.
- **D2 — Memory systems must be finished and public.** HMC, ENGRAM, DREAM,
  episodic, autobiographical, semantic, governance, provenance, consent, replay,
  revision, retention, export/import, corruption recovery are approved for public
  release. They are **not** dangerous merely for being advanced. Do **not**
  reclassify HMC/ENGRAM/DREAM to private to resolve registry inconsistency —
  instead finish them, reconcile registry with reality, add tests/evidence, label
  research maturity honestly. (Registry updated: HMC/ENGRAM/DREAM →
  `implementation_status: partial`, `public_release_target: CAPT_core`.)
- **D3 — Puter KV + mesh sync stay PRIVATE.** Local consent policy/records/
  enforcement, local export/import, safe abstract sync interfaces, disabled-by-
  default interfaces, non-network test doubles, and extension-point docs are
  PUBLIC. Puter KV impl, mesh-network impl, private coordination protocols,
  private credentials/endpoints, private infra adapters are PRIVATE and excluded.
  If public code depends on private transports, introduce a clean optional boundary
  so the public package works fully without them.
- **D4 — PULSE public, RYS private.** PULSE approved for public release if safe,
  documented, disabled-by-default where network exists, explicit about deps,
  tested, honest about maturity, free of private creds. RYS remains private
  (far from finished); no RYS code/datasets/checkpoints/orchestration in public
  artifacts. Generic interfaces useful independent of RYS may stay.
- **D5 — Do NOT publish.** No push to public repo, no public GitHub release, no
  PyPI, no public tags, no artifact upload, no deploy. Owner triggers publication.
  Local commits to the private branch are fine; local RC tags allowed if clearly
  marked non-published.
- **D6 — MIT approved for this safe public release.** Keep MIT; reconcile all
  metadata/headers/docs/release files. No conflicting license terms. Future fuller
  or private-derived versions may use a separate personal license; that does not
  apply retroactively unless owner says so. Do not copy private-source material
  into the MIT package unless explicitly approved.

## Boundary table (canonical)

| Class | Ships in public wheel? | Subsystems (evidence) |
|-------|------------------------|------------------------|
| PUBLIC | Yes | All `CAPT_core` with code in tree: MemoryEngine, CSG, ECHO, Semantic, Procedural, Prospective, Context, Search, Dedupe, Normalize, AntiToken, Retrieval Feedback, TTL, Temporal, Export/Import, Migration, HMC (partial), ENGRAM (partial), DREAM (partial), Identity, Reasoning Core, Ontology (doc), Constitution (doc), Hermes Plugin, Foundry/Governance/Proof, KHSB, CTP, CLI, Runtime SDK, **Mathematics/Physics/Invention engines (new, this session)**, local Consent (abstraction), local Sync (abstraction), PULSE (optional, disabled-by-default). |
| RESEARCH (spec, no code in tree) | No | FILT, FSR, NEDA, CONS, QIPC, OUROBOROS, CIG, HDR, META, Cognitive Loop, PLAST, ALLO, +30 registry modules — all `implementation_status: missing`, external repo. Documented as specifications/roadmap. |
| EXTERNAL | No (separate pkg) | RYS Bridge (private per D4), CAPTLANG. |
| OPTIONAL | No (opt-in) | PULSE (public optional, disabled-by-default). |
| PRIVATE (excluded) | No | Puter KV impl, mesh-network impl, private coordination, private creds/endpoints, RYS impl/datasets/checkpoints/orchestration, owner-private tooling. **None present in tree** (verified). |

## Automated drift detection

`tests/test_release_boundary.py` asserts:
- No module/import/symbol/file referencing `rys`, `puter`, `mesh`, or private
  coordination appears in the public `capt_solo/` tree.
- Registry `public_release_target` for HMC/ENGRAM/DREAM is `CAPT_core`.
- The built wheel excludes any private-named path.
- Public code imports succeed with private packages absent.

## What this session will NOT do

- Will not modify the MIT decision (D6).
- Will not include RYS/Puter/mesh (D3/D4).
- Will not push or publish (D5).
- Will not present missing research modules as complete (D1).

## Verification

- `find capt_solo -type d` for reasoning/cig/hdr/meta/neda/consc/qipc/ouroboros/
  filt/fsr/rys/puter/mesh → **empty** (no private/research code in tree).
- `grep -rn "rys\|puter\|mesh"` over `capt_solo/` source → only in docs/comments
  where explicitly labeling things private/excluded; no imports.
- `architecture/validate_registry.py` → 15 checks pass after HMC/ENGRAM/DREAM
  reconciliation.
- `capt workspace validate` → 0 fail.
