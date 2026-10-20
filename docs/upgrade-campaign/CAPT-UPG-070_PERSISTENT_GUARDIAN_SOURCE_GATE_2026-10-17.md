# CAPT-UPG-070 — persistent Guardian source attestation (phase 1)

Date: 2026-10-17
Scope: isolated CAPT Core candidate, **not** production deployment.

## Observed vulnerability
UPG-069 patched embedded-IPv4/IPv6 SSRF in Guardian source. Persistent
allowlist Guardian containers can predate that patch. Prior to this change,
persistent inspection validated image ID, topology, labels and sandbox flags,
but did not validate the Guardian Python source baked into Docker Config.Cmd.
start_persistent() constructed a *fresh* guardianSourceDigest from today's
module and supplied it to _start_guardian(), but the old container would
start its previously captured Python -c command. A fresh receipt digest
was therefore not proof of patched code inside the container.

## Bounded remedy
- During persistent Guardian inspection, require Docker Config.Cmd to be
  [profile.guardian_python, "-c", exact current Guardian source].
- Hash the command source and freshly loaded Guardian module source with
  SHA-256. Refuse missing, malformed, inconsistent or stale evidence.
- The same inspection runs before start_persistent() and exec_persistent(),
  so stale leases cannot be deliberately resumed or used through those APIs.
- Fail-closed error says "recycle required"; **no automatic recycle, new
  lease, approve, or replay**. Existing lease IDs remain traceable.
- Do not alter canonical policy, capability/lease digests or UPG-069 floors.

## Test evidence
- Red-first new test file: 8 failures on original code.
- After repair: 8/8 new tests passed, followed by 69/69 focused
  persistent-sandbox/guardian, network and lease-service tests.
- Tests use synthetic Docker inspection records; no real Guardian container,
  persistent lease, network socket, cloud settlement or model call involved.

## Remaining explicit gates (UPG-070 phase 2)
- A read-only inventory of all durable sandbox leases and matching Docker
  guardians, recording stored policy/source digest, actual Config.Cmd digest,
  Docker instance identity and active/stopped/unknown states.
- Ensure an old Guardian that remains running can be quarantined or shut
  down by a separate, exact HumanApproval-bound operation. This patch
  prevents CAPT-side reuse but cannot itself stop already-running egress.
- Prove that closed and unknown-remote leases are never silently replayed.
- Confirm genuine Docker Config.Cmd shape on macOS Docker Desktop and Linux;
  Cloud Run/gVisor socket and NAT64 routing remain unverified.
- Independent adversarial reviewer and full GitHub release/contract/security
  gates before merge. No unrestricted paid or cloud traffic is authorized.

## Authority
The user's approval is **in principle** for preparing UPG-070 first.
No production sandbox may be recycled or a paused mission resumed on that
basis alone. Specific lease ID(s), current state, protected scope and
exact HumanApproval are separate requirements.


## Cleanup safety follow-up (2026-10-19)
The original close_persistent path called inspect_persistent and therefore
refused the exact stale Guardian it needed to remove. The close path now
checks current workload identity, immutable image identity, expected labels,
UID/capability and network topology, but permits a stale Config.Cmd only
inside this separately authorized, existing sandbox.close effect. Start,
exec and normal inspection continue to reject stale Guardians. Cleanup
still verifies container and network absence; no automatic retry, recycle,
or lease recreation is added. Real Docker and exact-approval tests remain
release prerequisites.


## 2026-10-19 Docker Entrypoint verification
Docker combines image Config.Entrypoint with Config.Cmd. A Cmd digest
alone is not proof of the executed interpreter when an image-defined
Entrypoint can override the command. Persistent Guardian source
attestation now also requires an absent or empty Config.Entrypoint.
Synthetic tests explicitly reject shell and interpreter entrypoints.
This is still not a real daemon/immutable-image execution receipt.


## 2026-10-19 creation-time attestation completeness
The image may specify Config.Entrypoint independently of Config.Cmd.
The Guardian creation attestation now checks the exact source-bearing
Config.Cmd and requires Config.Entrypoint to be absent/empty before any
new Guardian may start. Existing persistent reuse applies the same check.
Two original synthetic Guardian inspect fixtures needed their missing
Docker Cmd/Entrypoint fields added; the workload fixture was unchanged.
Tests explicitly exercise malicious creation-time entrypoints. The
focused persistent/guardian/lease/network suite passed 76 tests.
Release still requires actual engine proof and per-lease authority.


## 2026-10-19 live Docker Desktop lifecycle evidence

Verified against actual Docker Engine 29.8.0 on desktop-linux, ARM64.
The locally available pinned python:3.13-slim image
(sha256:9d2e5553305c7c7b0097999bb17187c69b921ccd6bc9d40e4bb5ebe652c00285)
has no image Entrypoint. CAPT Node needed explicit PATH including
/usr/local/bin, where Docker CLI is installed; the daemon was already up.

The new test_real_guardian_source_drift_blocks_reuse_but_allows_exact_lease_cleanup
creates a uniquely labeled temporary persistent sandbox and allowlist Guardian,
checks created-state attestation, starts the Guardian and workload, simulates
source drift via test-only in-memory override, verifies normal inspection
rejects stale source, then exercises close-only exact identity cleanup.
Workload and Guardian IDs are proven absent and lease labels empty. No
external HTTP requests; test includes its own owned-resource cleanup in finally.

Real integration suite: 8 passed, 1 deselected in 15.27 seconds,
across both real Docker modules. The deselected test reaches external
example.com and is not necessary to prove container lifecycle cleanup.

Read-only Docker inventory had zero containers labeled capt.sandboxLeaseId.
Older unrelated SN118, Onyx and N8N Docker containers were not modified.
This is local Docker Desktop evidence, not Cloud Run/gVisor equivalence,
proof of global lease absence or model-operation authorization.
