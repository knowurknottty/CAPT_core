# InversionSandbox R2 Verification — 2026-09-09

## Scope

This note verifies the persistent governed `SandboxLease` boundary implemented on `feat/inversion-sandbox-r2`, building on merged R1 commit `e35635b74f24cfda6c60ee4904e57567ee8aa30b`.

R2 adds bounded persistent sandbox lifecycle, governed persistent exec, restart reconciliation, expiry/orphan handling, and real-Docker adversarial acceptance. It does not add execd, credentials, snapshots, PTY, browser/VNC, or mutable caller-owned egress policy.

## Local Docker Identity

All real-Docker verification used the already-local image `python:3.13-slim`; no image pull was performed.

- Image ID: `sha256:9d2e5553305c7c7b0097999bb17187c69b921ccd6bc9d40e4bb5ebe652c00285`
- Repo digest: `python@sha256:9d2e5553305c7c7b0097999bb17187c69b921ccd6bc9d40e4bb5ebe652c00285`
- Guardian test image: same already-local `python:3.13-slim`
## Focused R2 Gate

Command used the project venv with `CAPT_DOCKER_TEST_IMAGE=python:3.13-slim` and `CAPT_INVERSION_GUARDIAN_IMAGE=python:3.13-slim` across the SandboxLease aggregate/service, persistence backend, lifecycle tool, persistent exec, reconciliation, and persistent real-Docker suites.

Result: **142 passed in 5.06s**.

The real-Docker tranche proves:

- one governed sandbox remains alive across separately governed execs;
- tmpfs state persists across execs while capability consumption remains per command;
- close removes the exact lease-owned runtime object while preserving authorized host bind-mount contents;
- host exec timeout with unproven in-container termination quarantines the lease and requires explicit close;
- a create crash while the durable lease is still `reserved` can rediscover the exact stopped container only by the already-durable lease label and exact immutable bindings;
- persistent `none` networking remains unroutable even when Docker Desktop adds opaque `NetworkID`/`EndpointID` bookkeeping after start.
## R1 / Non-Regression Gate

The R1 Docker backend, InversionSandbox security/runtime/network/real-Docker suites, ToolBroker, and ToolExecution suites were rerun with the same local images.

Result: **59 passed in 12.90s**.

No R1 one-shot fallback, security-attestation, guardian, or broker regression was observed.

## Complete Repository Gate

Command:

`CAPT_DOCKER_TEST_IMAGE=python:3.13-slim CAPT_INVERSION_GUARDIAN_IMAGE=python:3.13-slim /Users/knowurknot/CAPT_core/.venv/bin/python -m pytest -q -rs`

Result: **1,687 passed, 13 skipped, 12 deselected in 80.39s**.

All 13 skips are existing live-UI tests that require a separately running CAPT runtime: UI CLI, continuity demo, desktop surface, onboarding, and TUI headless/live-runtime cases. No R2 Docker or sandbox test was skipped in the focused gate.
## Reconciliation and Authority Cases

The combined R2 unit/integration suites additionally cover:

- operator/session/profile/immutable-runtime identity mismatch denial;
- expired or non-running lease denial;
- replaced container/image, guardian drift, and unexpected network attachment rejection;
- non-root/no-privilege persistent exec and parent-environment noninheritance;
- create reservation before Docker mutation and atomic `reserved -> created` effect observation;
- atomic capability + ToolExecution + SandboxLease create/close settlement;
- unobserved create uncertainty becoming `indeterminate` instead of being silently retried;
- close from `created`, `running`, and `indeterminate`, including idempotent repeated close receipts;
- dedicated `sandbox.close` capability enforcement, including cleanup authority;
- restart reconciliation at `reserved`, `created`, `running`, `closing`, and `indeterminate` states;
- orphan CAPT-labeled objects reported without automatic adoption or deletion;
- expiry never extending the original resource TTL.
## Contract and Hygiene Gates

- Contract generation wrote **0 changed files**.
- Drift check: **OK — 11 generated files match the schema source**.
- `git diff --check`: clean.
- Ruff on the new handwritten R2 reconciliation/lifecycle/persistent-exec/real-Docker files: **all checks passed**.
- Base-vs-R2 Ruff comparison against `e35635b` shows **0 new handwritten-code violations**. The only additional diagnostics are 17 mechanically generated `capt_contracts/types.py` style findings for the three new generated sandbox schema types; generated bindings were not hand-edited.

## Resource Leak Proof

After the complete repository suite:

- CAPT-labeled containers (`label=capt.sandboxLeaseId`): **0**
- `capt_inv_*` internal networks: **0**
- `capt_guard_*` guardian containers: **0**

Unrelated host containers/resources were not modified.

## Conservative R2 Boundary

R2 intentionally remains conservative where proof is unavailable. In particular, a host-side `docker exec` timeout does not prove termination of the in-container process; the ToolExecution and SandboxLease are quarantined as `indeterminate` and further exec is blocked until reconciliation or explicit governed close. Missing or ambiguous Docker objects are never recreated or adopted under an existing lease identity.
