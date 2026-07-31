# CAPT Core v0.5 — Release Verification Report

Generated: 2026-07-30. Candidate SHA: `7b9bcf422c69d3afbbe600d64239c6dd8c3cea71`
(prior to Phase A blocker correction; SHA updates after the correction commit.)

## Scope
Documents the verification evidence for the CAPT Core v0.5.0 release candidate.
All figures below were regenerated at the candidate SHA, not copied from prior
reports.

## Test evidence (regenerated)

| Suite | Result |
|---|---|
| Full suite `pytest tests/ -q` | 711 passed, 4 failed, 44 skipped |
| Freeze-gate regression `test_release_identity_option_a.py` | 3 failed (require clean frozen tree) |
| Freeze-gate `test_release_semantics.py::test_live_release_semantics_pass` | 1 failed (requires frozen candidate_sha) |
| VSI `tests/ -k vsi` | 14 passed |
| ContextPack `tests/ -k contextpack` | 12 passed |
| Doctor injection | 5 passed |
| Security/token/injection | 35 passed |

### Note on the 4 failures
The 4 failing tests are Option A freeze-model regression tests. They clone the
repository, set `candidate_sha` to a real commit, and run `validate_release(
final=True)`. They fail in the current UNFROZEN state because:
- the working tree contains untracked release-audit evidence documents
  (Pass 3/4 deliverables), which the clone inherits and which fails the
  `candidate.clean_tree` check; and
- `candidate_sha` is `UNFROZEN`, so `candidate.sha_match` cannot pass.

These are EXPECTED failures in an unfrozen, dirty-tree state. They are not
implementation defects. They are designed to pass only after the candidate is
frozen (clean tree + `candidate_sha` set to the frozen commit). The freeze step
is owner-gated and occurs after this workflow.

## Release validator

| State | Command | Result |
|---|---|---|
| Pre-correction | `capt release validate` | 10 pass / 1 fail (`public_api.package_inventory` — manifest omitted `capt_solo.components`) |
| Post-correction | `capt release validate` | 10 pass / 0 fail |

The pre-correction failure (F1) was caused by OD-4 recovering
`capt_solo.components` (ATE) without updating the manifest's declared package
list. Corrected in Phase A by adding `capt_solo.components` to
`PUBLIC_API_MANIFEST_V0.5.json` stable packages.

## Package artifacts (built at candidate SHA)

| Artifact | SHA-256 |
|---|---|
| `capt_solo-0.5.0-py3-none-any.whl` | `e9e316464916a5ae97a4306ba15ad87dc1b191ee49d4cb047e9a9950248a3ba9` |
| `capt_solo-0.5.0.tar.gz` (sdist) | `92962c3b26687a61391593caba5ae0ea58a96c44374761616ba421d95189c480` |

## Reproducibility
Two independent builds are required (Phase C). This report records the first
build hashes; Phase C will confirm byte-identity or explain any difference.

## Verification commands for an end user
```
python3 -m pytest -q
python3 verify_runtime.py
python3 -m capt_cli release validate
python3 -m build
```

## Classification
Generated release evidence. No new public claim beyond code/test/runtime evidence.
