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
- **Computed enforcement report:** `ENFORCED_FOR_DECLARED_EFFECT_SET` for all 15 **declared Node service-identity staging effects** on real-user Linux and macOS JUnit. File: `docs/evidence/r04/enforcement_linux_macos.json` (computed from hashed receipts). This is **not a production enforcement claim**; parallel uid-501 surfaces and deployed Commander remain unsafe.
- **Rollback:** implemented. The staged rollback, revocation and crash restart passed, but the 20/20 script result concealed a residual macOS service-user record; the **full teardown gate remains open** until the corrected installer is rerun successfully.
- **Remaining blockers:** macOS Node staging 16/16 and Interop split-uid 13/13 passed. Staging drill now has 19/20 original and 20/20 corrected receipts, but **the service-account deletion postcondition failed independently**; macOS privacy/Directory Services permission issue remains. Live edge, bridge and TIA exposures persist; production cutover requires owner approval.

## Security test report (summary)

| Suite | Where | Result | Evidence |
|---|---|---|---|
| Node service identity, real users | Linux root sandbox | 16/16 | `docs/evidence/r04/linux_node_service_identity_20261106T052112Z.xml` (sha256 f4842699…df41b) |
| same, CI job | GitHub Actions (0fe4e1b1) | success | run on PR #254 |
| same, real macOS users | Mac (macOS 26.4.1, Core fac6ad0e, `_captnodestg` uid 450) | **16/16, 0 failures, 0 skips; exit 0; live process table unchanged**; independently inspected JUnit and SHA-256 | `docs/evidence/r04/macos_node_service_identity_20261106T145636Z.{txt,xml}` (Mac originals byte-identical) |
| Deployment kit drill | Mac | **PARTIAL:** original 19/20 (SIGKILL not treated as crash), corrected script 20/20 (SIGSEGV restart and EACCES proven), but hidden staging user persisted after uninstall | `docs/evidence/r04/macos_install_drill_20261106T172331Z.txt`, `...173125Z.txt`; see `MACOS_STAGING_DRILL_20261106.md` |
| Keychain argv fix | Linux / macOS | 13+1 skip / 14/14 | PR #255 |
| Bridge runtime gate + credential guard | Linux | 81 pass, 1 pre-existing | PR #20 |
| R0.3 split-uid regression | Mac (Interop 6f3d6412, Core c417a835) | **6/13 FAIL**: harness orphaned the runtime on stop (sudo cannot relay SIGKILL), state lock blocked the restart; cascade. Not an authority bypass | `CAPT-Interop/evidence/macos_split_uid_20261106T150004Z.*` on the Mac |
| same, harness fixed | Linux (Core c417a835) | 13/13, no runtime left behind | Interop PR #3 (80f307be + PID safety hardening at 1614a1b9) |
| same, harness fixed (real macOS rerun) | Mac (Interop 1614a1b9, Core c417a835) | **13/13 PASS**, zero failures, errors or skips; no disposable runtime survives | Interop PR #3 `evidence/r04/macos_split_uid_20261106T160426Z.{txt,xml}`; verified original Mac SHA-256 below |

## CI / repo ledger

| Repo | Branch / PR | Head | State |
|---|---|---|---|
| CAPT_core | `feat/r04-capt-node-service-identity` / #254 (draft) | see PR | CI green at 0fe4e1b1; later pushes queued |
| CAPT_core | `fix/r04-keychain-state-key-argv` / #255 (draft) | c417a835 | CI green (11 checks) |
| inversion-commander | `feat/r04-bridge-runtime-gate` / #20 (draft) | a815662b | GitGuardian green; no Actions workflows in this repo |
| CAPT-Interop | `fix/r04-split-uid-runtime-lifecycle` / #3 (draft) | 6574acc3 | harness stop/lock fix (80f307be), exact-runtime identity check before SIGKILL (1614a1b9), macOS 13/13 evidence (0ffe88ad), receipt records checkout SHAs (6574acc3); CI 6/6 |

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
| RR-15 | LOW (unassessed) | The macOS receipt shows the service account in implicit groups `everyone`, `localaccounts`, `com.apple.sharepoint.group.1/.2` and `_lpoperator` (nested membership; the 502 agent shows the same). Whatever those groups grant on this Mac, the service holds | Enumerate what the sharepoint groups and `_lpoperator` grant (`dscl . -read /Groups/com.apple.sharepoint.group.1`, File Sharing settings) before cutover |
| RR-16 | MEDIUM / STAGING GATE BLOCKER | The macOS staging uninstaller silently suppressed Directory Services user deletion failures; a disposable UID 450 account persisted despite 20/20 script assertions | Fixed error masking and postcondition checks in Core #254; macOS root deletion still returns eDSPermissionError (-14120). The full teardown gate is not met; explicit owner-controlled macOS authorization is needed. |
| RR-17 | LOW (availability) | On macOS 26.4.1 a SIGKILLed service Node is **not** restarted (`KeepAlive {Crashed}`; drill run 17:23:31Z, launchd log "exited due to SIGKILL … service inactive"); SIGSEGV is restarted. A jetsam/OOM or operator SIGKILL therefore leaves Commander without a Node until `launchctl kickstart -k system/online.inversionlabs.capt-node` | Fail-safe (never recovers as uid 501). Monitor `install.sh status`; decide whether `KeepAlive` should also cover `SuccessfulExit=false` — which would also restart a preflight refusal (exit 3), so it is not adopted |

## Final acceptance gates

| Gate | Status | Basis |
|---|---|---|
| Identity | PARTIAL | Linux and macOS 16/16 real-user **staging** proven; production still uid 501 |
| Human token | PARTIAL | Unreadable by the service (Linux); still held by the Commander runtime plane |
| Human IPC | PARTIAL | R0.4 macOS split-uid rerun **13/13 PASS** at Interop 1614a1b9 + Core c417a835; production still runs legacy principal |
| Agent IPC | PARTIAL | same real-user macOS 13/13 rerun, but agent-principal production rollout pending |
| Tool authority | PARTIAL | Scope ceiling enforced (Linux); bridge allowlist in #20, not deployed |
| Approvals | FAIL | RR-1 live |
| Attestations | FAIL | RR-1 live |
| CAPT-Bot | FAIL | RR-2 live |
| Filesystem | PARTIAL | Linux and macOS Node service-identity staging tested; production still exposed through uid-501 surfaces |
| Credentials | PARTIAL | #255 (macOS-proven) and #20 not deployed; RR-8 live |
| Concurrency | PARTIAL | Linux and both macOS staging suites passed; production not yet proven |
| Recovery | PARTIAL | macOS crash SIGSEGV restarted under UID 450; service rollback passed. Complete staging user teardown remains unproven |
| Linux E2E | PASS | 16/16 local + CI |
| macOS E2E | PASS | Node service identity 16/16 and split-uid regression 13/13 with zero skips; deployment/rollback drill tracked separately |
| Commander | FAIL | deployed edge and bridge stale |
| Rollback | PARTIAL | macOS service/daemon revocation passed, but hidden staging account survived after suppressed dscl deletion error; patched cleanup pending rerun |
| Source integrity | FAIL | deployed Commander ≠ `main`; edge unpinned |
| Production | NOT TESTED | not authorized for activation |

## Verdict

**PARTIAL — SPECIFIC GATES REMAIN.**

The architecture holds wherever it was tested with real users, and no gap needs a redesign. The failing gates are live deployment state: a stale edge Worker and bridge, a Node not yet cut over, and uid-501 surfaces outside the three repos. The Node service-identity macOS receipt is now verified and included in the staging enforcement computation; the patched split-uid regression subsequently passed 13/13 on macOS. The corrected drill demonstrated crash restart and socket denial but the independent account-delete postcondition failed; staging cleanup remains a release gate. RR-1 and RR-2 exist today, independent of R0.4, and close with cutover §2.

## November 6 — Mac evidence verification (R0.4 staging only)

The exact original Mac receipt files were hashed, parsed and copied byte-for-byte into `docs/evidence/r04/`. JUnit: 16 tests, 0 failures, 0 errors, 0 skips. The text receipt ends in `live runtime: unchanged (same pids, uids, start times)` and `exit: 0`. SHA256 TXT `92f464900a64c5cc5ac3cf9f9a18640b1a7ca5ef339451c317296ffac15750e4`; XML `0bbdb7cccc75d261de359b777ebc351274db2de9ed816d22443e0f5b6880bc2d`. This is bounded evidence for the 15 declared effects, not for production isolation.

## macOS Interop regression rerun — success after process-lifecycle fix

At Interop checkout `1614a1b930ef5992cfcc416dd386b5b22d566a35` (PR #3) and Core checkout `c417a8352d08e113980715175c61657efbebf1f2` (PR #255), the 2026-11-06T16:04:26Z owner-authorized macOS split-uid suite finished **13/13** (failures=0, errors=0, skipped=0) and left no disposable RuntimeService process. Raw receipt SHA-256: TXT `689c98025076122b8449e0c72381235fb144512c735c94ef1c3070401144ed4e`; XML `f7f4c6c564496b82912ae742018fdef9611980db75d697cc77c862981ce1cc0a`. Note: the sudo-generated receipt itself omitted checkout commit SHAs due to Git safe-directory restrictions; these revisions were independently recorded immediately before and after the test. The prior 6/13 run is retained as failure evidence. Staging drill remains owner-only and not run.

## November 6 — staging drill receipts and cleanup audit

The original 19/20 and corrected 20/20 macOS staging drill receipts are preserved with SHA-256 in `docs/evidence/r04/` alongside `MACOS_STAGING_DRILL_20261106.md`. The SIGSEGV crash restart was observed from PID 2198 to PID 2415 under UID 450 after 10 seconds; the agent socket received OS EACCES while the human connected. **However, the hidden _captnodestg user record survived `uninstall`**, and an administrator-authorized `dscl` removal returned eDSPermissionError (-14120). The script now fails closed on residual account records; a new privileged drill using that change has not passed. **Do not promote the 20/20 script receipt into a complete-cleanup claim.**
