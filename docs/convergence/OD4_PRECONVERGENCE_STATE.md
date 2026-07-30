# OD4_PRECONVERGENCE_STATE

Generated: 2026-07-30 (OD-4 execution). Pre-convergence evidence capture.

| Field | Value |
|---|---|
| repository path | /Users/knowurknot/capt-solo |
| current branch | integration/capt-v05-release-corrected |
| integration HEAD | 1a089ba2f34438a78505322f261926f61ad6ef8c |
| main HEAD | 55e149bbb078b197429ee21d02e8e3265b551e6e |
| merge base | abeff5c1fcb498533bce70448c069e59f4f0c8a0 |
| commits unique to integration | 69 |
| commits unique to main | 29 |
| Python (system) | 3.9.6 (NOT used) |
| Python (venv) | 3.12.13 (used for all validation) |
| package version | 0.5.0 |
| release metadata | candidate_sha UNFROZEN (pre-freeze, by design) |
| working tree | CLEAN (excluding untracked .capt_state/) |
| remotes | origin (public CAPT_core), preservation (private backup) |
| safety tag | od4-rollback-1a089ba |
| temp convergence branch | od4-converge-tmp (forked from 1a089ba) |

## Ancestry relationship
integration and main diverged at `abeff5c1` (v0.4.0). They are DISJOINT
SUPERSETS: integration carries the entire v0.5 architecture (66 net unique
commits); main carries ATE + gitleaks + release-security CI + whitepaper +
docs-refresh (29 unique commits). No preserved release-identity history
(3888f08 → be4b0da → 716ecc9 → 1a089ba) is rewritten by this convergence; the
integration lineage is the base and main's 10 unique files are recovered into it.

## Stop condition
Expected base lineage proven (716ecc9 ancestor of 1a089ba ancestor of HEAD).
Proceed to Phase 2.
