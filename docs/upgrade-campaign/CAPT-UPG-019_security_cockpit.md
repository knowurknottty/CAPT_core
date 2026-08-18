# CAPT-UPG-019 — Security Closure Cockpit

- **Campaign ID:** `CAPT-UPG-019`
- **Issue:** #86
- **PR:** #87
- **Base:** verified CAPT-UPG-018 @ `5ae86e80e53fa85b12fd29f45c5b25a575ac3aeb`
- **Disposition:** `IMPLEMENTED_VERIFIED_READY_FOR_OWNER_REVIEW`

## Scope

UPG-019 is a read-only projection over the existing `capt_runtime.security_gate` evaluator. It does not run arbitrary scanners, mutate RuntimeService, grant release authority, or claim that CAPT is universally secure.

The Cockpit exposes per control:

- control ID/title;
- status: PASS / FAIL / NOT_VERIFIED / N/A;
- severity;
- release-blocking flag;
- whether it blocks the current gate;
- exact supplied source SHA;
- evidence references;
- stale vs missing-evidence classification;
- reason/detail.

## Fail-closed projection hardening

The inherited projection was strengthened during reconciliation:

- a claimed PASS with no source SHA is downgraded to NOT_VERIFIED;
- a claimed PASS with no evidence reference is downgraded to NOT_VERIFIED;
- projection-created release blockers force the displayed gate decision back to BLOCKED;
- N/A remains distinct from PASS;
- stale evidence remains NOT_VERIFIED and visibly stale;
- `releaseAuthorized` is always false in this view;
- `globalSecurityVerdict` is always null.

The normal evaluator already requires exact-head source SHA + refs + verifier for PASS/FAIL `SecurityEvidence`; the extra projection checks defend against malformed or hand-crafted upstream result dictionaries.

## Real repository baseline

`security/profiles/capt-core.json` describes the current local runtime profile. The committed evidence file is intentionally empty/fail-closed because committed evidence cannot attest its own exact commit SHA without self-invalidating.

Observed against the current source SHA before commit:

```text
gate_rc=2
cockpit_rc=2
decision=BLOCKED
PASS=0
FAIL=0
NOT_VERIFIED=20
N/A=26
blockingControls=20
```

This is the truthful expected local baseline until exact-head release CI generates ephemeral verification evidence. It is not a product-security verdict.

## Surface

`desktop.security_cockpit` / `capt-security-cockpit` provides:

- headless deterministic JSON;
- Tk/Aqua control table;
- detail inspector for reason/evidence/source binding;
- explicit reminder that PASS is control/evidence scoped and does not authorize release.

The command exits 0 only when the underlying checklist gate is PASS; BLOCKED exits 2.

## Pre-commit verification

```text
DRIFT CHECK: OK (11 generated files match the schema source)
focused security cockpit/gate/evidence gate: 17 passed
full non-slow suite: first run had 1 intermittent desktop reconnect failure; isolated rerun passed; immediate full rerun passed 1017 / 13 skipped / 12 deselected
```

The transient desktop reconnect failure is outside UPG-019's changed files and was not reproducible in isolation or immediate full rerun. It is recorded rather than erased.

## Exact-head verification and package acceptance

Implementation head before this evidence-only update: `4b62cdc8199f4cf9e0b634412a250199dfc48e9b`.

```text
DRIFT CHECK: OK (11 generated files match the schema source)
focused security cockpit/gate/evidence gate: 17 passed
full non-slow suite: 1017 passed, 13 skipped, 12 deselected
```

Installed wheel from that exact implementation head:

```text
upg019_installed_imports=PASS
capt-security-cockpit --help: PASS
upg019_installed_headless=PASS rc=2 decision=BLOCKED
counts={PASS:0, FAIL:0, NOT_VERIFIED:20, N/A:26}
upg019_installed_tk_smoke=PASS
```

The installed headless command intentionally exits 2 because the committed evidence baseline is empty/fail-closed. That is the expected truthful result, not a failed acceptance.

No claim extends to repository tests excluded by the `slow` marker, to CI checks not executed locally (for example hosted gitleaks/pip-audit jobs), or to universal product security. Drift/focused/full gates are rerun after this final evidence-only commit.
