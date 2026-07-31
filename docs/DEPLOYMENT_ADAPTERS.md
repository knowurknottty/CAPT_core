# Governed Deployment Adapters

CAPT Core governs deployment tools; it does not replace them.

A deployment adapter wraps an existing deployment command, script, CI entrypoint,
or infrastructure tool with CAPT-owned transaction boundaries, evidence capture,
verification, rollback, and lifecycle controls.

## What CAPT owns

- named actor and reason
- target and artifact declaration
- explicit plan digest
- allowlisted executable invocation
- bounded timeout
- preflight validation
- CTP begin, validate, commit, and abort semantics
- verification evidence
- rollback attempt and result
- truthful capability status

## What the external tool owns

- provider-specific authentication
- infrastructure API calls
- artifact transfer
- rollout mechanics
- backend-specific health checks
- provider-specific rollback commands

## Adapter lifecycle

Every adapter implements:

```text
plan -> preflight -> execute -> verify
                         |
                         +-> rollback on failure
```

CAPT records each phase in the append-only CTP journal. A failed execution or
verification aborts the transaction. When a rollback command exists, CAPT attempts
it before finalizing the abort receipt.

## Reference adapter

`LocalScriptDeploymentAdapter` is the vendor-neutral reference implementation.
It invokes an existing local executable without a shell and requires an explicit
executable allowlist.

Security properties:

- no shell interpolation
- argv-based subprocess execution
- explicit executable allowlist
- resolved working directory
- bounded timeout
- minimal inherited environment
- stdout and stderr stored as hashes rather than copied into receipts
- dry-run mode by default

## Example

```python
import sys
from capt_solo.ctp.journal import CTPRuntime
from capt_solo.deployment import (
    DeploymentRequest,
    GovernedDeploymentExecutor,
    LocalScriptDeploymentAdapter,
)

adapter = LocalScriptDeploymentAdapter([sys.executable])
request = DeploymentRequest(
    adapter="local-script",
    target="staging",
    artifact="dist/capt_solo.whl",
    command=[sys.executable, "scripts/deploy.py", "staging"],
    verify_command=[sys.executable, "scripts/verify_deploy.py", "staging"],
    rollback_command=[sys.executable, "scripts/rollback.py", "staging"],
    actor="release-engineer",
    reason="publish reviewed staging candidate",
    dry_run=True,
)

with CTPRuntime() as ctp:
    result = GovernedDeploymentExecutor(ctp).run(adapter, request)
```

## Capability status

A successful fixture or dry-run establishes only that the adapter contract and
governance path behaved as expected.

It does **not** establish that a real production deployment works. The result
therefore retains:

```text
production_proven = false
```

Production proof requires evidence from a named backend, a real artifact, the
verification command, and—where claimed—the rollback path.

The honest progression is:

```text
candidate
-> validated against fixtures
-> approved
-> published
-> production verification pending
-> proven after real deployment evidence
```

## Adding a provider-specific adapter

1. Implement `DeploymentAdapter`.
2. Keep provider credentials outside the skill definition and evidence payload.
3. Return structured evidence for execution, verification, and rollback.
4. Add fixture tests for success, failure, timeout, and rollback.
5. Feed the deployment procedure through the Skill Foundry lifecycle.
6. Do not mark the capability proven until real backend evidence satisfies its
   declared proof requirements.

> Governance surrounds capability; it does not replace capability.
