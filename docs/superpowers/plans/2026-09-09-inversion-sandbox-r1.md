# InversionSandbox R1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a CAPT-native hardened local sandbox that proves applied Docker isolation before start and provides fail-closed none/allowlist/unrestricted network policy without weakening `terminal.docker`.

**Architecture:** Extend the existing Docker substrate only with opt-in security flags whose defaults preserve current behavior. Build `InversionSandboxProcessBackend` as a wrapper that compiles hardened profiles, attests the created container during Docker's existing pre-start observation point, and enriches side-effect identity. Allowlist mode uses a per-run Docker `--internal` network plus a dual-homed Python guardian proxy as the only egress path.

**Tech Stack:** Python 3.12+, pytest, Docker CLI/Engine on macOS Docker Desktop, stdlib `socket`, `selectors`, `ipaddress`, `hashlib`, canonical JSON.

**Spec:** `docs/superpowers/specs/2026-09-09-inversion-sandbox-r1-design.md`

## Global Constraints

- Base commit: `9ba26bc303f625b4c426a03a0620f5d14dffad53`.
- `terminal.docker` observable behavior and existing defaults remain unchanged.
- No implicit Docker image pulls.
- No Docker socket passthrough, privileged mode, host networking, or hidden authority.
- Sandbox results remain evidence only; HumanApproval/ToolExecution/verification/ClaimGuard semantics remain unchanged.
- Allowlist may never degrade to unrestricted bridge.
- Do not claim gVisor/Kata/Firecracker on the current host.

---
### Task 1: Add opt-in Docker hardening primitives without changing defaults

**Files:**
- Modify: `capt_runtime/tools/backends/docker.py`
- Modify/Test: `tests/capt_runtime/test_docker_tool_backend.py`

**Interfaces:**
- Produces `DockerTmpfsMount(path: str, size_bytes: int, noexec=True, nosuid=True, nodev=True)`.
- Extends `DockerProfile` with `user: str | None`, `cap_drop: tuple[str, ...]`, `no_new_privileges: bool`, and `tmpfs: tuple[DockerTmpfsMount, ...]`, all defaulting to current behavior.

- [ ] **Step 1: Write RED tests** proving a configured profile emits numeric `--user`, `--cap-drop ALL`, `--security-opt no-new-privileges:true`, and bounded tmpfs flags, while an ordinary profile still emits none of them.

```python
hardened = DockerProfile(..., user="65532:65532", cap_drop=("ALL",), no_new_privileges=True,
    tmpfs=(DockerTmpfsMount("/tmp", 64 * 1024 * 1024),))
assert hardened.user == "65532:65532"
```

- [ ] **Step 2: Run the focused tests and verify RED.**

Run: `/Users/knowurknot/CAPT_core/.venv/bin/python -m pytest -q tests/capt_runtime/test_docker_tool_backend.py`

- [ ] **Step 3: Implement the minimal validated fields and CLI emission.** Numeric user/group only; tmpfs paths must be absolute container paths and sizes in `[1 MiB, 1 GiB]`; duplicate tmpfs paths reject.

- [ ] **Step 4: Re-run focused Docker tests and verify GREEN.**

- [ ] **Step 5: Commit:** `feat(docker): add opt-in sandbox hardening controls`.
### Task 2: Define hardened profiles, policy compiler, and attestation

**Files:**
- Create: `capt_runtime/tools/backends/inversion_sandbox.py`
- Create/Test: `tests/capt_runtime/test_inversion_sandbox_security.py`

**Interfaces:**
- `InversionSandboxNetworkPolicy(mode: str="none", allow: tuple[str, ...]=(), platform_deny: tuple[str, ...]=DEFAULT_PLATFORM_DENY)` with `.canonical()` and `.digest()`.
- `InversionSandboxProfile(..., uid: int=65532, gid: int=65532, tmpfs_bytes: int=64*1024*1024, network_policy=...)` with `.docker_profile()` and `.security_profile_digest()`.
- `attest_created_container(profile, prepared, record) -> InversionSandboxAttestation`.

- [ ] **Step 1: Write RED unit tests** for invalid root UID/GID, forbidden `unrestricted` without explicit opt-in, canonical/deterministic policy digests, platform-deny precedence, seccomp readiness requirement, and a created-record mismatch such as `ReadonlyRootfs=False`.

```python
with pytest.raises(AuthorityViolation, match="non-root"):
    InversionSandboxProfile(..., uid=0)
with pytest.raises(AuthorityViolation, match="read-only rootfs"):
    attest_created_container(profile, prepared, weakened_record)
```

- [ ] **Step 2: Verify RED** with `pytest -q tests/capt_runtime/test_inversion_sandbox_security.py`.

- [ ] **Step 3: Implement canonical JSON hashing and strict profile validation.** Default platform denies include `169.254.169.254/32`, `169.254.0.0/16`, `127.0.0.0/8`, `0.0.0.0/8`, `::1/128`, and `fe80::/10`.

- [ ] **Step 4: Implement attestation** for image/container/state, user, readonly rootfs, `ALL` cap drop, no-new-privileges, resource limits, tmpfs, mounts, network mode, `Privileged=False`, empty devices, and forbidden namespace sharing.

- [ ] **Step 5: Verify GREEN and commit:** `feat(sandbox): add hardened profile attestation`.
### Task 3: Wrap Docker execution and expose `terminal.inversion_sandbox`

**Files:**
- Modify: `capt_runtime/tools/backends/inversion_sandbox.py`
- Create: `capt_runtime/tools/adapters/inversion_sandbox_terminal.py`
- Modify: `capt_runtime/tools/builtins.py`
- Modify: `capt_runtime/composition.py`
- Create/Test: `tests/capt_runtime/test_inversion_sandbox_runtime.py`
- Modify/Test: `tests/capt_runtime/test_tool_registry.py`, `tests/capt_runtime/test_runtime_tool_wiring.py`

**Interfaces:**
- `InversionSandboxProcessBackend.preflight(request) -> InversionSandboxPreparedTarget`.
- `InversionSandboxProcessBackend.execute(request, *, prepared=None, observe_effect=None) -> InversionSandboxProcessResult`.
- `InversionSandboxTerminalToolAdapter` mirrors the Docker adapter but requires `toolId="terminal.inversion_sandbox"`, `backendId="inversion_sandbox"`.

- [ ] **Step 1: Write RED tests** showing independent readiness/profile registries, no fallback to `terminal.docker`, and enriched identity keys `securityProfileDigest`, `networkPolicyDigest`, `filesystemScopeDigest`, `attestationDigest`.

- [ ] **Step 2: Verify RED** with the new runtime tests plus tool-registry tests.

- [ ] **Step 3: Implement wrapper execution.** Convert the hardened profile to an opt-in `DockerProfile`; pass a wrapper callback into the existing Docker pre-start `observe_effect` point; re-inspect the created container, attest it, and only then forward the enriched canonical identity to ToolExecution observation.

- [ ] **Step 4: Implement descriptor and composition wiring.** `create_runtime(..., inversion_sandbox_profiles=())` must register the tool even when readiness is unavailable.

- [ ] **Step 5: Verify focused runtime/tool tests and existing Docker tests GREEN.**

- [ ] **Step 6: Commit:** `feat(sandbox): wire governed inversion sandbox tool`.
### Task 4: Implement privilege-free allowlist guardian and internal-network orchestration

**Files:**
- Create: `capt_runtime/tools/backends/inversion_guardian.py`
- Modify: `capt_runtime/tools/backends/inversion_sandbox.py`
- Create/Test: `tests/capt_runtime/test_inversion_sandbox_network.py`

**Interfaces:**
- Guardian entrypoint: `python3 inversion_guardian.py`; reads bounded `CAPT_GUARDIAN_POLICY_B64`, binds TCP `18080`, prints `CAPT_GUARDIAN_READY <policyDigest>` only after listen succeeds.
- `destination_allowed(policy, host, resolved_ips) -> bool` applies immutable deny precedence before caller allow rules.
- Backend creates `capt_inv_<container-prefix>` using `docker network create --internal`, creates a hardened guardian on bridge, connects guardian to internal network as alias `capt-guardian`, and rewires the still-created workload from bridge to internal before attestation/start.

- [ ] **Step 1: Write RED policy/proxy tests** for FQDN wildcard, IP/CIDR rules, RFC1918/link-local/loopback denial, DNS-rebinding denial, malformed CONNECT/HTTP rejection, and deterministic policy digest.

- [ ] **Step 2: Verify RED** with `pytest -q tests/capt_runtime/test_inversion_sandbox_network.py`.

- [ ] **Step 3: Implement the stdlib guardian proxy.** Support HTTP absolute-form and HTTPS/TCP `CONNECT`; resolve in the guardian, connect to an allowed resolved IP directly, cap request headers at 64 KiB, and never expose a policy-mutation endpoint.

- [ ] **Step 4: Implement Docker orchestration.** Guardian image must be explicitly named and locally present; create with read-only rootfs, non-root UID:GID, `cap-drop=ALL`, no-new-privileges, bounded tmpfs, and no host mounts except the read-only guardian script if needed.

- [ ] **Step 5: Ensure ToolExecution observation occurs before guardian/workload start.** Network/containers may be created in stopped state; enriched effect identity is observed before starting the guardian, then guardian readiness is proven before the existing Docker backend starts workload code.

- [ ] **Step 6: On every failure/timeout, remove workload, guardian, and internal network; ambiguity becomes indeterminate evidence, never bridge fallback.**

- [ ] **Step 7: Verify network tests GREEN and commit:** `feat(sandbox): add isolated allowlist guardian`.
### Task 5: Real-Docker adversarial acceptance and repository regression gate

**Files:**
- Create/Test: `tests/capt_runtime/test_inversion_sandbox_real_docker.py`
- Modify: `docs/superpowers/specs/2026-09-09-inversion-sandbox-r1-design.md` only if implementation evidence reveals a contract correction.

**Interfaces:**
- Real tests use `CAPT_DOCKER_TEST_IMAGE` for workload and `CAPT_INVERSION_GUARDIAN_IMAGE` for guardian; tests skip truthfully when a required local image is absent.

- [ ] **Step 1: Write RED real-daemon tests** that inspect the workload during the created-state callback and assert non-root user, readonly rootfs, cap-drop ALL, no-new-privileges, limits, tmpfs, scoped mounts, and exact network attachment.

- [ ] **Step 2: Add adversarial cases** for parent-secret noninheritance, direct external connection failure in allowlist mode, allowed proxy destination success, denied private/link-local destination failure, timeout cleanup, and forced attestation mismatch proving `docker start` is never called.

- [ ] **Step 3: Run focused real-Docker tests** with local images only. No `docker pull` is permitted by the test harness.

- [ ] **Step 4: Run regressions:**

```bash
/Users/knowurknot/CAPT_core/.venv/bin/python -m pytest -q tests/capt_runtime/test_docker_tool_backend.py tests/capt_runtime/test_inversion_sandbox_security.py tests/capt_runtime/test_inversion_sandbox_runtime.py tests/capt_runtime/test_inversion_sandbox_network.py tests/capt_runtime/test_inversion_sandbox_real_docker.py
/Users/knowurknot/CAPT_core/.venv/bin/python -m pytest -q tests/capt_runtime
/Users/knowurknot/CAPT_core/.venv/bin/python -m pytest -q
```

- [ ] **Step 5: Run hygiene:** targeted Ruff on modified Python files and `git diff --check`.

- [ ] **Step 6: Record exact counts, Docker image IDs/digests, skipped tests, and any unverified allowlist cases in the final verification note.**

- [ ] **Step 7: Commit:** `test(sandbox): prove inversion sandbox security boundary`.