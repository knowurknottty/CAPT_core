# R0.4 — Sovereign authority isolation: checkpoints, test report, ledger, risks, verdict

Mission CAPT-R04-TRIPLE-RECURSION. Architecture: `docs/security/R04_NODE_SERVICE_IDENTITY.md`.
Cutover: `deploy/macos/capt-node/CUTOVER.md`. Evidence: `docs/evidence/r04/`.
"Pending owner run" means a macOS `sudo` step the agent cannot perform.

## Checkpoint R1 — architect

- **Source revision:** Core `feat/r04-capt-node-service-identity` 1e46dc65 → 10e75f02.
- **Authority graph revision:** r1.
- **Claims tested:**
  - Node runs as a dedicated uid.
  - Remote exec can't read the human token, home or signing key.
  - It can't rewrite trust, config or code.
  - The agent can't reach the socket.
  - Receipts survive a restart.
  - Unsafe deployments refuse to start.
- **Tests executed:** real-user E2E 12/12 (Linux, root sandbox, `cnode-svc/human/agent`); unit 11/11; legacy Node 50/50; full Core suite 2546 pass / 27 fail. The same 27 fail on `main` fb0f38a in this sandbox (root user, no OpenSSH, TUI), so none are regressions.
- **Observed failures (fixed):** service-created files didn't inherit the client group, so the state dir is now setgid. The restart test assumed replay; reuse with a different request is in fact refused.
- **Changes:** `capt_runtime/node/service.py`; serve wiring; CI job `capt-node-service-identity` (runs as root, `CAPT_NODE_E2E_REQUIRED=1`).
- **Unverified assumptions:** macOS group-membership refresh for long-running uid-501 processes; per-item Keychain ACLs.
- **Remaining blockers:** macOS real-user run (pending owner run).

## Checkpoint R2 — adversarial

- **Source revision:** Core 0fe4e1b1 (#254), c417a835 (#255); Commander a815662b (#20).
- **Authority graph revision:** r2. New edges found: remote caller → edge → bridge → runtime MCP (human token); remote caller → read roots → credential files; uid-501 parallel surfaces.
- **Attack classes and results:**

| Class | Attack | Result |
|---|---|---|
| Identity confusion | start the Node as the human or agent uid | refused at preflight (E2E) |
| Identity confusion | a Node-spawned process (service uid) drives its own Node | `NODE_PEER_UID_DENIED` (E2E) |
| Identity confusion | another paired controller reads `status` | fixed: bound to the issuing controller (unit) |
| Filesystem escape | symlink to the human token inside the workspace | Permission denied (E2E) |
| Filesystem escape | `cwd` through a symlink to trust | `filesystem_scope_violation` (E2E) |
| Filesystem escape | signed capability widening the roots | `NODE_CAPABILITY_ROOT_OUTSIDE_SERVICE_SCOPE` (E2E) |
| Process escape | double-fork + setsid child | **survives operation close**; service revocation kills it (E2E) |
| Authorization laundering | live edge `runtimeExec` includes `capt_approval_decide`, `capt_verification_decide`; bridge forwards to a runtime MCP holding the human token | **BLOCKER (live)**; Commander #20 adds a local refusal; edge redeploy pending |
| Authorization laundering | deployed bridge/TIA at c722e48 (pre-#19) still presses Authorize/Complete/Reconcile | **BLOCKER (live)** |
| Authorization laundering | read roots contain a Chrome profile (Cookies, Login Data) and other runtimes' tokens | Commander #20 refuses credential files by name after realpath |
| Credential confidentiality | state key in `security add-generic-password -w` argv; `TimeoutExpired` carries it | fixed in #255 (stdin via `security -i`); macOS real CLI 14/14 |
| Concurrency | six concurrent reuses of one operation id | dispatched once (E2E) |
| Concurrency | socket briefly wider than policy between bind and chmod | fixed: umask 0177 before bind |

- **Claims challenged from R1:**
  - "Receipts are durable": true, but **not tamper-proof**. `shell.exec` runs as the service uid and can rewrite `journal.sqlite` and `denials.jsonl` and read `node.key` (HIGH, see register).
  - "Cancel stops work": false for detached children; revocation is the boundary.
- **Tests executed:** E2E 15/15; unit 13/13; Keychain 13 pass + 1 skip (Linux) / 14/14 (macOS 26.4.1, Python 3.14.7); bridge 81 pass, 1 pre-existing sandbox failure (TIA stdio, also fails on `main`); edge 38/38.
- **Regressions:** none observed. R0.3 13/13 rerun on macOS is pending owner run.
- **Remaining blockers:** the two live laundering BLOCKERs (deployment actions); parallel uid-501 surfaces (unassessed).

## Checkpoint R3 — operational

- **Source revision:** Core ce445ad9 → be296359 → 3705feac. Commander a815662b.
- **Changes:** deployment kit (`install.sh`: prepare / operator / trust / activate / bridge-switch / retire-legacy / status / rollback / uninstall), LaunchDaemon template (restarts only after a crash, `-I` interpreter), hash-pinned wheels, `serve --preflight-only`, staging drill with four injected failures, computed enforcement report.
- **Supply chain:**
  - Node: exact commit via `git archive`, root-owned, `--require-hashes --only-binary`.
  - Edge: `package.json` pins nothing (`latest`); deploy from `npm ci` against the committed lockfile only.
  - Deployed bridge c722e48 ≠ `main`.
  - Deployed Node was untracked; imported verbatim with hashes (`docs/evidence/CAPT_NODE_IMPORT_PROVENANCE.md`).
  - Hermes not exercised (no plugin was deployed through the shared gateway).
- **Simulated remote Commander caller attempting a human-authority op:** done by inspection of the live manifest and by bridge unit tests. The live tool was **not** invoked: it would mutate the live runtime.
- **Computed enforcement report:** `PARTIAL` (Linux enforced for all 15 effects; macOS evidence missing). File: `docs/evidence/r04/enforcement_linux_only.json`.
- **Rollback:** implemented. The downgrade path needs `CAPT_NODE_ACCEPT_SAME_UID_EXPOSURE=YES`. Tested in the staging drill (pending owner run).
- **Remaining blockers:** macOS evidence (3 owner runs); live exposure (edge, bridge, TIA); production cutover (approval).

## Security test report (summary)

| Suite | Where | Result | Evidence |
|---|---|---|---|
| Node service identity, real users | Linux root sandbox | 16/16 | `docs/evidence/r04/linux_node_service_identity_20261106T052112Z.xml` (sha256 f4842699…df41b) |
| same, CI job | GitHub Actions (0fe4e1b1) | success | run on PR #254 |
| same, real macOS users | Mac | pending owner run | `deploy/macos/capt-node/staging-e2e.sh` |
| Deployment kit drill | Mac | pending owner run | `deploy/macos/capt-node/staging-drill.sh` |
| Keychain argv fix | Linux / macOS | 13+1 skip / 14/14 | PR #255 |
| Bridge runtime gate + credential guard | Linux | 81 pass, 1 pre-existing | PR #20 |
| R0.3 split-uid regression | Mac | pending owner run | `CAPT-Interop/scripts/setup_split_uid_macos.sh` |

## CI / repo ledger

| Repo | Branch / PR | Head | State |
|---|---|---|---|
| CAPT_core | `feat/r04-capt-node-service-identity` / #254 (draft) | see PR | CI green at 0fe4e1b1; later pushes queued |
| CAPT_core | `fix/r04-keychain-state-key-argv` / #255 (draft) | c417a835 | CI green (11 checks) |
| inversion-commander | `feat/r04-bridge-runtime-gate` / #20 (draft) | a815662b | GitGuardian green; no Actions workflows in this repo |
| CAPT-Interop | — | `main` 6f3d6412 | no R0.4 changes; regression harness only |

There are no merges, no force-pushes and no direct writes to `main`. The repositories stay private.

## Residual-risk register

| ID | Sev | Risk | State / remediation |
|---|---|---|---|
| RR-1 | BLOCKER | Live edge exposes `capt_approval_decide` / `capt_verification_decide`; bridge forwards with the human token | Open. Cutover §2a and §2b. #20 makes the bridge refuse locally |
| RR-2 | BLOCKER | Deployed TIA/bridge c722e48 allows human-only CAPT-Bot dispositions | Open. Cutover §2b |
| RR-3 | BLOCKER | Production Node runs as uid 501 with capability roots including `~/CAPT_core` and its own code | Open. Cutover §3–6 |
| RR-4 | BLOCKER | Parallel uid-501 remote surfaces (second Node, perplexity `node_bridge`, macos bridge with helm token, macos-control, actions gateway behind a public tunnel) | Unassessed; outside the three repos. Cutover §9 |
| RR-5 | HIGH | `shell.exec` shares the service uid with the Node server: it can rewrite the journal and denials and read `node.key` (no human authority gained) | Open. Remedy: separate execution uid (worker daemon accepting only the Node uid by peer cred). Until then, the authoritative record is controller-side (bridge audit log, uid 501) |
| RR-6 | HIGH | Detached children outlive operation close/cancel | By design of the executor. Revocation = `install.sh rollback` (proven Linux; macOS drill pending) |
| RR-7 | HIGH | Commander runtime plane authenticates as the human principal | Structural fix after a runtime upgrade past #253 (cutover §10) |
| RR-8 | MEDIUM | Read roots contain browser credentials and other runtimes' tokens | #20 guard; also move the TIA Chrome profile out of the read roots |
| RR-9 | MEDIUM | Edge dependencies unpinned (`latest`) | Pin versions; deploy from the lockfile |
| RR-10 | MEDIUM | Live runtime e4f72d4 predates #253 (no agent principal live) | Separate owner-approved release |
| RR-11 | LOW | Service venv interpreter is Homebrew's (owned by uid 501); a Homebrew upgrade can break it | No escalation (501 > service). Re-run `prepare` after Python upgrades |
| RR-12 | LOW | `denials.jsonl` grows without bound under an allowed peer | Rotate by the operator; no truncation by the service |
| RR-13 | LOW | `CAPT_STATE_KEY_B64` override readable by the same uid (`ps -E`) | Test and harness use only |
| RR-14 | LOW | Live Commander capability is 24 h and refreshed manually | After cutover: re-run `install.sh operator`, which re-signs the capability and leaves an active pairing untouched (drilled in `staging-drill.sh`) |

## Final acceptance gates

| Gate | Status | Basis |
|---|---|---|
| Identity | PARTIAL | Linux real-user proven; macOS pending; production still uid 501 |
| Human token | PARTIAL | Unreadable by the service (Linux); still held by the Commander runtime plane |
| Human IPC | PARTIAL | R0.3 13/13 macOS; R0.4 regression pending |
| Agent IPC | PARTIAL | as above |
| Tool authority | PARTIAL | Scope ceiling enforced (Linux); bridge allowlist in #20, not deployed |
| Approvals | FAIL | RR-1 live |
| Attestations | FAIL | RR-1 live |
| CAPT-Bot | FAIL | RR-2 live |
| Filesystem | PARTIAL | Linux proven; macOS pending |
| Credentials | PARTIAL | #255 (macOS-proven) and #20 not deployed; RR-8 live |
| Concurrency | PARTIAL | Linux proven; macOS pending |
| Recovery | PARTIAL | Revocation proven on Linux; launchd crash drill pending |
| Linux E2E | PASS | 16/16 local + CI |
| macOS E2E | NOT TESTED | pending owner run |
| Commander | FAIL | deployed edge and bridge stale |
| Rollback | NOT TESTED | implemented; drill pending |
| Source integrity | FAIL | deployed Commander ≠ `main`; edge unpinned |
| Production | NOT TESTED | not authorized for activation |

## Verdict

**PARTIAL — SPECIFIC GATES REMAIN.**

The architecture holds wherever it was tested with real users, and no gap needs a redesign. The failing gates are live deployment state: a stale edge Worker and bridge, a Node not yet cut over, and uid-501 surfaces outside the three repos. Pending macOS evidence keeps the rest at PARTIAL. RR-1 and RR-2 exist today, independent of R0.4, and close with cutover §2.
