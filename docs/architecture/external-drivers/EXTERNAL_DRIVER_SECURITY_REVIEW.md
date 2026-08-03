# External Driver Security Review (Gate A — OpenHarness)

## Scope

Security assessment of integrating the genuine OpenHarness 0.1.9 harness as an
external CAPT ExecutionDriver, executed via local Ollama.

## Threats assessed

| # | Threat | Mitigation | Status |
|---|--------|------------|--------|
| 1 | External driver identity spoofing | `observedBy` must equal registered driver id (ingestion) | PASS (test) |
| 2 | Wrong adapter/driver version | descriptor `driverId`+`driverVersion` immutable in registry | PASS |
| 3 | Forged CAPT event / capability grant / verification / ClaimGuard | `reject_fabricated_authoritative` blocks all 6 authoritative types | PASS (test) |
| 4 | Forged completion claim | harness cannot emit completion; CAPT owns completion | PASS (design) |
| 5 | Cross-mission observation | `workOrderId` must match run | PASS (test) |
| 6 | Duplicate / conflicting duplicate | `seen` map rejects conflicting payloads | PASS (test) |
| 7 | Observation sequence rollback | single-shot; no sequence to roll back | N/A |
| 8 | Stale / revoked lease | `verify_lease` checks status/revoked/validity | PASS (test) |
| 9 | Scope escalation | lease path scope enforced; filesystemPolicy writesAllowed=false | PASS (test) |
| 10 | Path traversal / symlink escape | `_realpath_within` rejects escapes | PASS (test) |
| 11 | Artifact substitution | digest verified against file | PASS (test) |
| 12 | Receipt substitution | `driverRunId` checked | PASS (test) |
| 13 | Context over-disclosure | ContextSlice excludes governance/ledger; sentinel test at ingestion | PASS (design+test) |
| 14 | Environment-variable leakage | sandbox strips all hosted keys; minimal allowlist | PASS (design) |
| 15 | Unauthorized network call | only 127.0.0.1:11434 reachable; verified via Ollama log | PASS (verified) |
| 16 | Unexpected subprocess | harness invoked with fixed argv; cwd=target; no shell | PASS (design) |
| 17 | Driver / adapter / Ollama crash | adapter raises `OpenHarnessExecutionError`; CAPT does not promote | PASS (design) |
| 18 | Runtime restart / orphaned process | lifecycle tracks proc; reconcile maps unknown→external_state_unknown | PASS (design) |
| 19 | Replay after completion / cancellation | terminal state recorded; re-dispatch is a new run id | PASS (design) |
| 20 | Removal regression | base imports work without openharness pkg; reference driver intact | PASS (test) |

## FINDING (residual): max-use exhaustion not enforced

`verify_lease` does NOT check `used >= maxUses`. A lease with `used` already at
`maxUses` is still accepted. This is a gap in the FROZEN M0-B capability
enforcement code, not a contract schema defect.

- Evidence: `test_lease_max_use_exhausted_rejected` is marked `xfail` (expected
  failure) documenting the gap.
- Impact: a driver could exceed its granted max-use count if `used` is not
  incremented/checked externally. In the Gate A proof, each run uses a fresh lease
  id, so the practical impact is low, but the control is missing.
- Disposition: NOT fixed here — modifying frozen M0-B enforcement requires a
  separate ADR + owner authorization (mission constraint: do not modify frozen
  CAPT contracts without explicit authorization). Recorded for follow-up.

## Credential handling

- All hosted keys (ANTHROPIC_*, OPENAI_*, GITHUB_TOKEN, SSH_AUTH_SOCK, AWS_*,
  GOOGLE_*, AZURE_*, and gateway keys) are removed from the `oh` subprocess env.
- The only API key reaching the harness is the non-secret placeholder
  `ollama-local` for the localhost Ollama endpoint.
- No CAPT secret is ever passed to the external process.

## Network isolation

- Observed: only `127.0.0.1:11434` (Ollama) contacted during execution.
- No egress to hosted LLM APIs, package registries (during run), or external
  services.

## Third-party code risk

- OpenHarness is MIT third-party code executed as a subprocess. It is not
  embedded in CAPT and no upstream source is copied into the repo.
- Risk mitigated by: separate process, minimized env, read-only task, digest
  verification, and CAPT-owned authority. A full source audit of OpenHarness is
  out of scope for Gate A.

## Secret scan

- No secrets in `capt_runtime/external_drivers/` or `docs/architecture/external-drivers/`.
- The placeholder `ollama-local` is a non-secret local value.
