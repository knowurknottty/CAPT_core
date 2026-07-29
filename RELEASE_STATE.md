# RELEASE_STATE.md — Release Readiness

- **package**: `capt-solo`
- **version**: `0.5.0`
- **candidate_sha**: `UNFROZEN`
- **release_status**: `HARDENING — NOT RELEASE READY`
- **publication_status**: `NOT PUBLISHED`
- **license**: MIT; `LICENSE` is included in source distributions.
- **release boundary**: public CAPT Core runtime and documented package data;
  no credentials, private coordination services, user state, or `.capt_state/`.

## Gate status

| Gate | State | Evidence authority |
|---|---|---|
| Packaging inventory | Implemented; final rerun pending | `tests/test_distribution_contract.py` |
| Installed CLI and profiles | Implemented; final rerun pending | `capt doctor`, `tools/profile_smoke.py` |
| Public architecture/API | Drafted; validation pending | ADR-0008 through ADR-0012 |
| Semantic freshness | In progress | `capt release validate` |
| Verification-first tutorial | Pending | tutorial test and output bundle |
| Security closure | Pending | canonical scan and dependency audit |
| Exact candidate evidence | Pending | frozen-SHA evidence bundle |
| Owner publication | Withheld | ADR-0007 |

## Release rule

A previous audit, historical test total, local build artifact, or successful
source-tree import is not release evidence for this candidate. Release readiness
requires all gates to be rerun against one frozen candidate and the resulting
failures to be closed or explicitly accepted by the owner.

## Current decision

**NOT RELEASE READY. NOT PUBLISHED.**
