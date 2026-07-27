# ADR-0007 — Owner Release Decisions for CAPT v0.4.1 Public Release

- **Status:** Accepted (owner-approved, 2026-07-27)
- **Supersedes:** none (new)
- **Related:** ADR-0001 (architecture governs implementation), ADR-0003
  (memory biologically inspired), ADR-0005 (local-first optional network),
  ADR-0006 (evidence over implementation)

## Context

The repository reached RELEASE CANDIDATE. The owner issued six binding decisions
governing the public release boundary, the treatment of memory systems, and the
scope of the mathematics/physics/invention engines. These decisions resolve the
previously open [B]/[S] owner gates.

## Decisions

1. **Research modules may be public if real.** FILT, FSR, NEDA, CONS, QIPC,
   OUROBOROS approved for public release where actually implemented, safe,
   accurately described, and tested. Missing modules stay documented specs, not
   presented as production capability. Truthfulness mandatory.
2. **Memory systems finished and public.** HMC, ENGRAM, DREAM, episodic,
   autobiographical, semantic, governance, provenance, consent, replay, revision,
   retention, export/import, corruption recovery approved for public release. Do
   **not** reclassify HMC/ENGRAM/DREAM to private to resolve registry
   inconsistency; finish them and reconcile the registry with reality.
3. **Puter KV + mesh sync private.** Local consent/sync abstractions public;
   Puter KV, mesh, private coordination, credentials, endpoints private and
   excluded. Public package must function without private transports.
4. **PULSE public, RYS private.** PULSE approved (safe, disabled-by-default,
   tested, honest). RYS remains private; excluded from public artifacts.
5. **Do not publish.** No push/public release/PyPI/public tag/artifact upload/
   deploy. Owner publishes manually. Local commits and clearly-marked local RC
   tags permitted.
6. **MIT approved for this safe public release.** Keep MIT; reconcile metadata/
   headers/docs. No conflicting terms. Future private/full versions may use a
   separate personal license without retroactive effect.

## Consequences

- The public/private boundary is now decided, not pending. `RELEASE_GOVERNANCE.md`
  is the canonical boundary record; `architecture/registry.yaml` is the
  machine-readable companion.
- HMC/ENGRAM/DREAM remain `CAPT_core` (not private) with `implementation_status`
  reconciled to `partial` (code exists in-tree).
- RYS/Puter/mesh are excluded by absence (none in tree) and guarded by
  `tests/test_release_boundary.py`.
- The session's primary implementation focus is the mathematics, physics, and
  invention engines plus memory convergence.

## Validation

- Registry HMC/ENGRAM/DREAM entries updated to `partial` + `capt-solo` paths.
- `tests/test_release_boundary.py` added to detect future private-code drift.
- `architecture/validate_registry.py` remains green (15 checks).
