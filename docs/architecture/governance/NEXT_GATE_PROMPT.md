# Next Gate Prompt (prepared, not executed)

This is the recommended next program step and the exact prompt to launch it.
Do NOT begin it in this pass.

## Recommended next step: Option A — Accept and merge M0-B later

Selected because:
- M0-B is independently proven (M0B_INDEPENDENT_REVIEW.md).
- PR #23 has no blocking defects (M0B_ACCEPTANCE_DECISION.md).
- The CI "Release Security" failure is conclusively unrelated / properly
  dispositioned (RELEASE_SECURITY_DEPENDENCY_DECISION.md).
- The unauthorized skill mutation is contained (POST_M0B_GOVERNANCE_INCIDENT_REPORT.md).
- Documentation is accurate.

Options B/C/D/E were considered and rejected for *this* gate:
- B (correct M0-B defects): no real defect found.
- C (resolve CI first): CI fix is recommended but is a separate, out-of-M0-B
  change (workflow edit) requiring its own authorization; it should not block
  M0-B acceptance since the relevant conformance suites pass.
- D (implement RuntimeAggregate): explicitly deferred; not justified yet
  (POST_M0B_RUNTIMEAGGREGATE_ADR_PROPOSAL.md recommends a RuntimeManifest, not a
  new aggregate).
- E (begin M0-C): forbidden until M0-B is merged and explicitly authorized.

## Exact prompt for the next gate

```
You are continuing the CAPT Runtime program. M0-B (Read-Only ExecutionDriver
Proof) is independently reviewed and accepted pending merge: see
docs/architecture/governance/M0B_ACCEPTANCE_DECISION.md and
docs/architecture/governance/M0B_INDEPENDENT_REVIEW.md.

Authorized next action: merge draft PR #23
(feat/capt-runtime-m0b-readonly-driver-proof-hy3 ->
feat/capt-runtime-m0a-contract-state-proof) after owner review. Do NOT merge to
main unless M0-A is first merged to main. Do NOT begin M0-C. Do NOT implement
RuntimeAggregate.

Before merging, optionally: (1) run `ruff format` on the 3 noted M0-B files for
style consistency; (2) confirm CI "M0-A Contract & Runtime Proof" suites stay
green; (3) verify the PR base is still the proven M0-A branch and HEAD is
0d851c4535d2f93c3420f4c6d860f4ecd7285163.

Separately (different PR, different authorization): address the Release Security
CI failure per docs/architecture/governance/RELEASE_SECURITY_DEPENDENCY_DECISION.md
(Option 4+5: split required vs optional security jobs; allow the optional
anti-token-extraction suite to be non-green/skipped when its private dependency is
unavailable). Do not let that CI red block the M0-B merge decision.

Report the merge result and stop.
```

## Gate readiness
- M0-B: ready for merge (accepted pending merge).
- RuntimeAggregate: design proposed; implementation deferred to a separate
  authorized effort.
- M0-C: not started; requires M0-B merge + explicit authorization.
