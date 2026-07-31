# MICRO_AUDIT_REPORT — Phase B

Candidate SHA: `be2863508e47c3cb9ea4b4320ebab29bdcf64d94`
Date: 2026-07-30. Governing: captstreasurechest docs/16_V0_5_POST_AUDIT_RELEASE_WORKFLOW.md (Phase B).
Working dir: /Users/knowurknot/capt-solo. Python: .venv (3.12.13).

## Decision: PASS — proceed to artifact build and portability validation

## Checks (all PASS)

### B1 — `capt release validate` passes at corrected SHA
- Command: `.venv/bin/python -m capt_cli release validate`
- Exit: 0
- Output: 10 checks `status: pass`, 0 `status: fail`
  (authority.required_paths, version.identity, schema.identity,
  public_api.package_inventory, packaging.discovery_contract,
  authority.live_state_freshness, authority.release_status,
  public_api.no_sole_facade_claim, authority.changelog_pointer,
  candidate.manifest_state)
- SHA: be28635

### B2 — manifest matches source/wheel/sdist/installed inventories
- source subpkgs (19): components contextpack continuity core ctp engines
  evidence execution foundry khsb knowledge learning lifecycle memory
  ontology plugin research verification
- wheel subpkgs (19): identical to source
- manifest declared (union stable+provisional+experimental, 19): identical,
  now includes `capt_solo.components`
- installed wheel top packages: include `components` (and internal modules
  api/pulse/release_validation/workspace which are submodules, not separate
  packages)
- Conclusion: all four inventories agree; `capt_solo.components` present in all.

### B3 — README links resolve
- `docs/security/RELEASE_SECURITY_REPORT_V0.5.md`: EXISTS
- `docs/release/RELEASE_VERIFICATION_V0.5.md`: EXISTS

### B4 — generated reports exist at advertised paths
- Both files present (see B3).

### B5 — reports derived from already collected evidence
- Security report cites: gitleaks (no leaks), verify_runtime (52/1/0),
  doctor injection (5 pass), security suite (35 pass), no-network import,
  zero-Hermes import, ATE verify_pinned_commit. All regenerated this session.
- Verification report cites: 711/4/44 test result, validator pre/post,
  artifact hashes. All regenerated.

### B6 — reports introduce no unsupported public claims
- Both reports explicitly state "no new public claim beyond code/test/runtime
  evidence." No capability, version, or support claim added.

### B7 — previous false validator-PASS statement corrected
- `docs/EXACT_SHA_RELEASE_VALIDATION.md` carries CORRECTION NOTICE; now states
  validator FAILED pre-correction, PASS post-correction.
- `docs/BASELINE_REVALIDATION.md` corrected: 711/4/44, validator FAIL→PASS.

### B8 — no unrelated file changed during blocker correction
- Correction commit `be28635` changed exactly 5 files:
  PUBLIC_API_MANIFEST_V0.5.json, RELEASE_SECURITY_REPORT_V0.5.md (new),
  RELEASE_VERIFICATION_V0.5.md (new), EXACT_SHA_RELEASE_VALIDATION.md,
  BASELINE_REVALIDATION.md. No source, API, or architecture change.

### B9 — candidate SHA recorded in every exact-SHA report
- EXACT_SHA_RELEASE_VALIDATION.md: be28635 (and notes 7b9bcf4 pre-correction)
- BASELINE_REVALIDATION.md: 7b9bcf4 (regenerated count)
- RELEASE_VERIFICATION_V0.5.md: 7b9bcf4
- RELEASE_SECURITY_REPORT_V0.5.md: 7b9bcf4

### B10 — working tree clean after evidence committed
- `git status` (excluding .capt_state/) = CLEAN at be28635.

## Artifact hashes (current dist, built at 7b9bcf4)
- wheel: e9e316464916a5ae97a4306ba15ad87dc1b191ee49d4cb047e9a9950248a3ba9
- sdist: 92962c3b26687a61391593caba5ae0ea58a96c44374761616ba421d95189c480

## Residual note
The 4 freeze-gate test failures (Option A regression) are EXPECTED in the
UNFROZEN/dirty state and are outside Phase A/B scope. They are not a micro-audit
failure. They become relevant at the owner freeze step (clean tree + frozen SHA).
