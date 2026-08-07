# 02 — Standalone CAPT Core Harness Functionality Audit

**Audit target:** CAPT Core Standalone Harness v0.5 (b79c4f0)
**Evidence base:** `/tmp/capt-release-evidence-b45c4b0*` and verification-fix log
**Installed wheel:** `capt_solo-0.5.0-py3-none-any.whl` (sha256 `348fe9da…`)

## Classification Legend

| Classification | Meaning |
|---|---|
| `PROVEN_BY_INSTALLED_ARTIFACT` | Exercised against the installed wheel; real runtime output observed |
| `PROVEN_BY_SOURCE` | Verified in source code; imported and/or contract-confirmed but not exercised in installed wheel |
| `REPORTED_ONLY` | Reported by tooling or logs but not independently verified |
| `PARTIAL` | Some evidence exists but gaps remain |
| `NOT_PROVEN` | No evidence found |
| `DEFERRED` | Out of scope for this audit cycle |

---

## Capability Classifications

1. **Installed service** — `PROVEN_BY_INSTALLED_ARTIFACT` — `capt harness start/health/capabilities/command/stop` over token-authenticated Unix socket, proven from installed wheel.

2. **Canonical composition** — `PROVEN_BY_SOURCE` — `capt_runtime.composition.create_runtime()` is the frozen composition root; imported and verified.

3. **Authenticated socket** — `PROVEN_BY_INSTALLED_ARTIFACT` — Token auth over Unix domain socket, proven in installed lifecycle.

4. **RuntimeClient** — `PROVEN_BY_INSTALLED_ARTIFACT` — Client connects, sends commands, receives responses through installed wheel.

5. **Health** — `PROVEN_BY_INSTALLED_ARTIFACT` — Health endpoint returns `HEALTHY`, integrity ok.

6. **Capabilities** — `PROVEN_BY_INSTALLED_ARTIFACT` — Advertises `run_fixed_openharness_inspection` and `run_approved_hermes_inspection`.

7. **Governed commands** — `PROVEN_BY_INSTALLED_ARTIFACT` — `create_mission`, `submit_approval_decision`, `cancel_task`, `cancel_driver_run`, `update_memory_trigger_policy`, `checkpoint_runtime`, `shutdown`, `resume_runtime` all exercised through installed wheel.

8. **EventStore mutation** — `PROVEN_BY_INSTALLED_ARTIFACT` — Ledger grew 0 → 13 → 26 → 39 events across installed lifecycle.

9. **Idempotency** — `PROVEN_BY_INSTALLED_ARTIFACT` — Conflicting idempotency payload rejected (`classification=idempotency`, fingerprint-conflict detail); replay returns idempotent without re-execution.

10. **Fixed-function OpenHarness execution** — `PROVEN_BY_INSTALLED_ARTIFACT` — `run_fixed_openharness_inspection` produces analysis artifact through installed governed path. This is a bounded, read-only repository inspection — NOT arbitrary model-driven engineering.

11. **Verification** — `PROVEN_BY_SOURCE` (improved) — `build_verification_result` now conforms to frozen contract after b79c4f0 repair; NOTE: installed wheel at b45c4b0 predates the repair; see Residual Backlog.

12. **ClaimGuard** — `PROVEN_BY_INSTALLED_ARTIFACT` — Bounded claim "Repository inspected in read-only mode." accepted; overclaim "The issue was fixed." rejected in adversarial battery.

13. **Checkpoint** — `PROVEN_BY_INSTALLED_ARTIFACT` — `checkpoint_runtime` creates checkpoint manifest in ledger.

14. **Stop** — `PROVEN_BY_INSTALLED_ARTIFACT` — `shutdown` command stops service cleanly.

15. **Second-launch refusal** — `PROVEN_BY_INSTALLED_ARTIFACT` — Second start on same socket/ledger refused.

16. **Restart** — `PROVEN_BY_INSTALLED_ARTIFACT` — Restart on same ledger succeeds, chain digest matches.

17. **Resume** — `PROVEN_BY_INSTALLED_ARTIFACT` — `resume_runtime` returns `not_repeated` (no re-execution).

18. **No-repeat behavior** — `PROVEN_BY_INSTALLED_ARTIFACT` — Idempotent replay of completed tasks returns stored result without re-execution.

19. **Package lifecycle** — `PROVEN_BY_INSTALLED_ARTIFACT` — Wheel built, installed `--no-deps` into fresh venv, imports from wheel proven.

---

## Wheel Provenance Note

The installed wheel (sha256 `348fe9da…`) was built from commit **b45c4b0**, which is **before** the verification-contract repair at **b79c4f0**. The wheel has **not** been rebuilt after the repair.

This means:
- Capabilities exercised through the installed wheel (items 1–10, 12–19) reflect the b45c4b0 codebase.
- The verification contract repair (item 11) is proven at source level (b79c4f0) but not yet present in any installed artifact.
- A rebuilt wheel from b79c4f0 is required to close this gap; see **Residual Backlog**.

---

## Summary Tally

| Classification | Count |
|---|---|
| `PROVEN_BY_INSTALLED_ARTIFACT` | 17 |
| `PROVEN_BY_SOURCE` | 2 |
| `REPORTED_ONLY` | 0 |
| `PARTIAL` | 0 |
| `NOT_PROVEN` | 0 |
| `DEFERRED` | 0 |
| **Total** | **19** |

Two capabilities are proven at source level only; the remaining seventeen are proven against the installed wheel artifact.
