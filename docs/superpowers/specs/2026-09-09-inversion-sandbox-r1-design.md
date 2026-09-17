# InversionSandbox R1 Design

## Problem

CAPT's existing `terminal.docker` backend is intentionally narrow and already enforces immutable image identity, local-only Docker contexts, bounded resources, scoped mounts, no Docker-socket passthrough, no implicit pulls, literal argv, timeout cleanup, and fail-closed networking.

The remaining gap is between `network=none` and explicitly unrestricted bridge networking, plus the absence of a CAPT-owned proof that Docker actually applied the requested security controls before untrusted code starts.

OpenSandbox demonstrates useful separation between lifecycle control, runtime backends, in-sandbox execution, and a dedicated network/security plane. Its Docker runtime also applies capability drops, `no-new-privileges`, seccomp/AppArmor controls, and optional secure runtimes. CAPT should adapt those primitives without importing OpenSandbox's lifecycle/control authority.

Upstream reference: `opensandbox-group/OpenSandbox` commit `473ff611d93670a149ce6600f27ed194b18cce89`, Apache-2.0.

## Decision

Add a new CAPT-native `terminal.inversion_sandbox` tool beside `terminal.docker`.

`terminal.docker` remains behaviorally unchanged and acts as the control. `terminal.inversion_sandbox` reuses the proven Docker execution substrate but requires a stronger immutable security profile and performs post-create/pre-start attestation against Docker's actual container state.

Configuration is not proof: if the created container does not match the authorized security contract, CAPT destroys it before start and records no successful execution.
## R1 Security Contract

Every InversionSandbox profile must enforce:

- local Unix-socket Docker context only;
- locally present immutable image identity; no implicit pull;
- read-only root filesystem;
- explicit non-root numeric UID:GID;
- `cap-drop=ALL`;
- `no-new-privileges=true`;
- bounded CPU, memory, PID count, stdout/stderr, timeout, and tmpfs;
- no privileged mode, devices, host PID/IPC/UTS/network namespaces, or Docker/Unix socket passthrough;
- writable host mounts only inside explicitly admitted host/container roots;
- ephemeral writable `/tmp` and `/run` tmpfs with `nosuid,nodev,noexec`;
- parent environment is not inherited;
- cleanup policy is always.

The host/runtime preflight must prove Docker reports seccomp enabled. R1 does not claim gVisor, Kata, or Firecracker because the current Docker Desktop runtime inventory exposes runc only.

An unavailable stronger runtime must be reported as unavailable, never silently approximated.
## Applied-Security Attestation

After `docker create` returns a container ID and before `docker start`, CAPT inspects the created container and verifies the applied state against the authorized profile.

The attestor verifies at minimum:

- container ID and immutable image ID;
- `State.Status == created`;
- `Config.User` equals the required numeric UID:GID;
- `HostConfig.ReadonlyRootfs == true`;
- `HostConfig.CapDrop` contains `ALL`;
- `HostConfig.SecurityOpt` contains `no-new-privileges:true` or Docker's normalized equivalent;
- configured CPU, memory, and PID limits;
- network mode equals the compiled network policy;
- expected tmpfs mount options and bounds;
- every mount is expected, in scope, and has the authorized RW/RO state;
- no devices, privileged mode, or forbidden namespace sharing.

The canonical attestation result is hashed. The ToolExecution side-effect identity binds `containerId`, `imageId`, `profileId`, `securityProfileDigest`, `networkPolicyDigest`, `filesystemScopeDigest`, and `attestationDigest`.

Any mismatch is an `AuthorityViolation`; cleanup is attempted immediately and execution never starts.
## Network Policy

The public policy vocabulary is `none`, `allowlist`, and `unrestricted`.

`none` maps to Docker network `none` and is always available when Docker is available.

`unrestricted` maps to bridge networking only when the profile explicitly opts into unrestricted egress. It is never selected as a fallback.

`allowlist` is default-deny. R1 compiles an immutable canonical policy containing explicit FQDN/IP/CIDR targets plus platform-deny overlays. Execution requires an explicitly configured, locally present guardian image; CAPT never pulls one implicitly.

CAPT creates a per-execution Docker `--internal` network. The workload is attached only to that network, which has no external route. A dual-homed guardian attaches to both the internal network and ordinary bridge networking and becomes the workload's only egress path. The workload receives no `NET_ADMIN` capability and cannot mutate policy. Platform-deny rules outrank caller/user allow rules.

If the guardian image, internal-network creation, guardian health, or policy enforcement prerequisites are unavailable, allowlist readiness fails closed. CAPT must not degrade `allowlist` to ordinary Docker bridge networking. The guardian requires no `NET_ADMIN`; local isolation depends on Docker network topology plus application-layer destination enforcement.

R1 platform-deny defaults include Docker/control sockets and link-local/cloud-metadata destinations. Host/LAN/private-address denial is configurable only through named CAPT profiles; a model-generated request cannot remove platform denies.
## Interfaces and Ownership

New public runtime types live under `capt_runtime.tools.backends.inversion_sandbox`:

- `InversionSandboxNetworkPolicy`
- `InversionSandboxSecurityProfile`
- `InversionSandboxProfile`
- `InversionSandboxProfileRegistry`
- `InversionSandboxProcessRequest`
- `InversionSandboxPreparedTarget`
- `InversionSandboxProcessResult`
- `InversionSandboxProcessBackend`

The implementation may extend the internal Docker substrate with additive security options and an attestation hook, but existing `DockerProfile` defaults and `terminal.docker` observable behavior must remain unchanged.

`capt_runtime.composition.create_runtime()` accepts `inversion_sandbox_profiles` independently from `docker_profiles`. The tool registry exposes `terminal.inversion_sandbox` independently; no routing rule may silently substitute one backend for the other.

CAPT's ToolBroker, authority grants, HumanApproval, ToolExecution, EventStore, result verification, and ClaimGuard remain authoritative. A sandbox process result is evidence only.
## Failure Semantics

- Missing profile: reject before Docker contact.
- Remote Docker context: reject.
- Image absent locally: reject; do not pull.
- Seccomp unavailable: hardened profile readiness is unavailable and preflight rejects.
- Security configuration rejected by Docker: return a failed process result or authority failure with no started workload.
- Created-container attestation mismatch: destroy container, raise `AuthorityViolation`, never call start.
- Cleanup ambiguity: surface `cleanup_succeeded=false` and preserve the container identity as evidence; never report clean completion.
- Allowlist guardian unavailable or unhealthy: reject before workload start; never fall back to bridge.
- Guardian policy application indeterminate: destroy workload/guardian where possible and return indeterminate control evidence.
- Runtime/daemon identity changes between preflight and execution: reject and require a new preflight.

## Verification Gate

R1 is accepted only after focused unit tests, real-Docker acceptance tests, existing Docker regression tests, runtime/tool-registry tests, targeted Ruff, `git diff --check`, and the full repository suite pass.

Real-Docker tests must inspect a container while it is still in `created` state and prove the hardened properties before CAPT starts it. Negative tests must deliberately request or simulate weakened settings and prove execution does not start.
## Attribution

Conceptual/runtime-security ideas adapted from OpenSandbox include the separation of runtime and security planes, capability dropping, `no-new-privileges`, secure-runtime readiness, and sidecar-owned egress policy. Any copied or materially adapted source must retain Apache-2.0 notices as required; this tranche should prefer independent CAPT-native implementation over source copying.

## Non-Goals

R1 does not add a second lifecycle server, OpenSandbox SDK compatibility, Kubernetes, pause/resume, snapshots, persistent sandbox leases, VNC/browser desktops, Jupyter/execd, credential injection, or live-cloud resources.

R1 does not install or claim gVisor, Kata, Firecracker, or another OCI runtime.

R1 does not weaken HumanApproval, ToolExecution, verification, or ClaimGuard semantics.

A later tranche may add persistent `SandboxLease` lifecycle and boundary credential injection only after this one-shot local boundary is proven.