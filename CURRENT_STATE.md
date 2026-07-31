# CURRENT_STATE.md — Authoritative Live State

> Read-only release semantics are enforced by `capt release validate`. Runtime
> behavior remains independently checked by `./verify.sh`.

- **branch**: `integration/capt-v05-final-audit`
- **candidate_sha**: `1cba134749ffc6bf3cb7eeb261e27b8e876ede41` (frozen via PUBLIC_API_MANIFEST_V0.5.json)
- **version**: `0.5.0`
- **release_status**: `HARDENING — NOT RELEASE READY`
- **publication_status**: `NOT PUBLISHED`
- **scope**: bounded P0 packaging, authority, public API, tutorial, security,
  and exact-candidate verification work only.
- **packaging**: recursive `capt_solo.*` discovery, `capt` console entry point,
  plugin manifest, and bundled skills are covered by distribution-contract
  tests.
- **public architecture**: six public pillars mapped onto the existing internal
  registry; see `docs/PUBLIC_ARCHITECTURE.md` and ADR-0008.
- **public API**: stability tiers and canonical evidence ownership are recorded
  in `docs/PUBLIC_API_STABILITY.md` and ADR-0009/ADR-0010.
- **completed release work**:
  - pre-remediation packaging baseline captured;
  - wheel/sdist package discovery repaired;
  - installed-artifact smoke profile and `capt doctor` added;
  - architecture and API authority reconciliation drafted.
- **open release gates**:
  1. semantic freshness and negative tests;
  2. installed-artifact verification-first tutorial;
  3. canonical security scan, dependency audit, and remediation closure;
  4. clean frozen-candidate build/install/test/evidence run.
- **owner gates**: publication remains withheld. No tag, merge, push, or package
  publication is authorized.
- **state boundary**: `.capt_state/` is pre-existing user state and is excluded
  from release work.
- **generated_at**: `2026-07-29`

Historical implementation reports and old release audits are evidence, not live
state. They do not override this file.
