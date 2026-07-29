# ADR-0010 — Public API Stability Tiers

- **Status:** Accepted
- **Date:** 2026-07-29
- **Supersedes:** the documentation rule that `capt_solo.api` is the sole
  sanctioned import path
- **Related:** ADR-0001, ADR-0004, ADR-0006

## Context

CAPT already documents and tests package-level APIs for Evidence, Verification,
ContextPack, Foundry, Workspace, and other subsystems. Calling every import
outside `capt_solo.api` an implementation detail contradicts that reality and
prevents honest compatibility promises.

## Decision

Public surfaces use four stability tiers:

- **Stable** — compatibility is maintained within the current major version;
  breaking changes require deprecation or migration.
- **Provisional** — public and tested, but may evolve through a documented
  deprecation path during the current major version.
- **Experimental** — research or demonstration surface; no general
  compatibility promise.
- **Internal** — not a public contract.

`capt_solo.api` remains a stable convenience and compatibility facade. It is not
the only valid public import path.

Every stable or provisional import must be present in wheel and sdist artifacts
and covered by installed-artifact tests. Persisted formats have an independent
schema-version promise even when the Python API is provisional.

## Evidence

- Package-level `__init__.py` files already export deliberate symbol sets.
- ContextPack v1 has a permanent canonical fixture.
- Evidence and VSI have explicit public package documentation and tests.
- The pre-remediation wheel proved that undocumented package discovery can
  violate source-level API claims.

## Consequences

- `docs/PUBLIC_API_STABILITY.md` is the human-readable inventory.
- Release tests derive artifact requirements from the declared public package
  set.
- Internal implementation remains free to evolve where no public tier is
  declared.

## Alternatives Considered

- Expanding `capt_solo.api` to re-export every subsystem was rejected because it
  would create a monolithic import boundary.

## Related Invariants

I-07, I-08, I-09, I-10, I-15.
