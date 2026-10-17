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
