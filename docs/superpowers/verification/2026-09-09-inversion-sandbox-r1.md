# InversionSandbox R1 Verification

Date: 2026-09-09
Branch: `feat/inversion-sandbox-r1`
Base: `9ba26bc feat(cloudflare): add durable workflows orchestration`

## Verified architecture

- New independent tool: `terminal.inversion_sandbox` / backend `inversion_sandbox`.
- Existing `terminal.docker` remains independently registered and behaviorally compatible.
- Hardened workload contract: non-root UID:GID, read-only rootfs, `cap-drop=ALL`, `no-new-privileges`, bounded CPU/memory/PIDs, bounded `noexec,nosuid,nodev` tmpfs, no devices, scoped mounts, and applied-state attestation before start.
- `none` network mode is fail-closed and accepts Docker Desktop's canonical `NetworkSettings.Networks={"none": ...}` representation only when it carries no endpoint/network/IP identity.
- Allowlist mode uses a per-execution Docker `--internal` network and a dual-homed, non-privileged guardian proxy. The workload is created directly on the internal network and never transiently attached to bridge.
- Platform deny rules outrank allow rules; DNS-rebinding candidates resolving to denied ranges are rejected.
- Effect observation occurs before guardian start; guardian readiness is then proven before workload start.
- Guardian and workload image use is local-only with `--pull never`; seccomp and guardian-image availability are enforced during preflight and rechecked at execution.
## Real Docker evidence

Local workload/guardian image:

- tag: `python:3.13-slim`
- immutable ID: `sha256:9d2e5553305c7c7b0097999bb17187c69b921ccd6bc9d40e4bb5ebe652c00285`
- repo digest: `python@sha256:9d2e5553305c7c7b0097999bb17187c69b921ccd6bc9d40e4bb5ebe652c00285`
- platform: `linux/arm64`
- Docker security options included `name=seccomp,profile=builtin`.

Real-daemon acceptance proved:

- workload remains `created` during CAPT effect observation;
- non-root/read-only/cap-drop/no-new-privileges/resource/network state is visible in Docker inspect before start;
- parent secret is not inherited;
- direct external connection from allowlist workload is blocked;
- allowed HTTP proxy traffic succeeds;
- allowed HTTPS `CONNECT` traffic succeeds;
- link-local metadata traffic is denied with HTTP 403;
- timeout removes workload, guardian, and internal network;
- forced attestation mismatch prevents workload start and leaves no marker effect.
## Test and hygiene gates

- Final focused Docker + sandbox real/unit gate: `43 passed`.
- `tests/capt_runtime`: `877 passed, 9 skipped, 12 deselected`.
- Final full repository, pinned project venv with real Docker images enabled: `1497 passed, 13 skipped, 12 deselected in 75.46s`.
- All 13 final skips are live UI/TUI/onboarding tests that require a separately running CAPT runtime.
- Contract drift: `DRIFT CHECK: OK (11 generated files match the schema source)`.
- Ruff comparison across 16 changed Python files versus base `9ba26bc`: zero new diagnostics.
- `git diff --check`: clean.
- Post-test Docker leak check: no `capt_guard_*` containers and no `capt_inv_*` networks remained.

## Deliberately unclaimed

- No gVisor, Kata, Firecracker, or alternate OCI runtime is installed or claimed; current Docker Desktop exposes runc with seccomp.
- No persistent sandbox lease/execd/snapshot lifecycle is included in R1.
- No live-cloud authority was crossed and no provider-side resource was created.
- The guardian supports HTTP proxying and TCP/HTTPS `CONNECT`; arbitrary non-proxied application protocols are intentionally not presented as allowlisted egress.
