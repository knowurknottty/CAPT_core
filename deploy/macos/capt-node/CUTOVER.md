# R0.4 production cutover package — CAPT Node service identity

**Status: prepared, not activated.** Every production step below needs the owner's explicit
approval. Nothing here is run by an agent. Each step names its consequence and how to verify it.
Commands assume a clean checkout of the approved Core commit at `~/capt-r04-release/CAPT_core`.

## 1. Preconditions (all must hold before step 3)

| # | Condition | How to check |
|---|---|---|
| P1 | Core PR #254 (service identity + kit) and #255 (Keychain argv) merged; CI green on the merge commit | GitHub checks on `main` |
| P2 | macOS real-user receipt `macos_node_service_identity_*.txt` exit 0, 16/16 | `deploy/macos/capt-node/staging-e2e.sh` |
| P3 | macOS drill receipt `macos_install_drill_*.txt` `fail=0` | `deploy/macos/capt-node/staging-drill.sh` |
| P4 | `scripts/r04_enforcement_report.py --junit linux=… --junit macos=…` → `ENFORCED_FOR_DECLARED_EFFECT_SET` | exit 0 |
| P5 | R0.3 split-uid regression 13/13 on macOS against the release commit | `CAPT-Interop/scripts/setup_split_uid_macos.sh agent --run …` |
| P6 | Commander PR #20 merged | GitHub |

## 2. Close the live human-authority exposure first (independent of the Node)

These two steps remove the BLOCKERs that exist **today**, before any Node change.

```
# 2a. Edge Worker from Commander main (removes capt_approval_decide / capt_verification_decide and
#     the TIA human-only buttons from the remote surface). Consequence: a Worker deploy; brief reconnects.
cd ~/capt-r04-release/inversion-commander && git checkout --detach <main-sha-including-#19-and-#20>
npm ci && cd apps/edge && npx vitest run && npx wrangler deploy
# verify: Commander get_capability_manifest → policy.runtimeExec has no *_decide tool

# 2b. Bridge + TIA on the Mac to the same commit (local refusal, credential-path guard, TIA bot fix).
#     Consequence: bridge restart (~seconds of Commander unavailability).
cd ~/capt-node-workspace/inversion-commander && git fetch origin && git checkout --detach <same sha>
npm ci && npm run build -w @inversion/commander-bridge && npm test -w @inversion/commander-bridge
launchctl kickstart -k gui/$(id -u)/online.inversionlabs.inversion-commander-bridge
```

## 3. Prepare the service Node (no change to the live Node)

```
cd ~/capt-r04-release/CAPT_core
sudo bash deploy/macos/capt-node/install.sh prepare --commit "$(git rev-parse HEAD)"
bash deploy/macos/capt-node/install.sh operator            # as you, no sudo
sudo bash deploy/macos/capt-node/install.sh trust          # ends with a passing preflight as _captnode
```

Consequences: creates hidden `_captnode` (uid 450–499, no shell, no home, no password, not admin)
and `captnodeclients` = {you, `_captnode`}; creates `/Library/CAPTNode`; adds an ACL granting you
read/write in `/Library/CAPTNode/workspaces/main`. Group membership applies to processes started
after this point (the bridge picks it up at its next restart in step 5).

## 4. Activate (owner approval)

```
sudo CAPT_NODE_ACTIVATE=I-APPROVE-R04-CUTOVER bash deploy/macos/capt-node/install.sh activate
sudo bash deploy/macos/capt-node/install.sh status
```

Activation refuses unless the preflight passes, then checks the **running** process's uid in the
process table (it boots the daemon out if that uid is wrong) and probes `id -u` as you. The legacy
uid-501 Node keeps running, so Commander still works.

## 5. Switch Commander to the service Node

```
bash deploy/macos/capt-node/install.sh bridge-switch        # backs up ~/.inversion-commander/config.json
launchctl kickstart -k gui/$(id -u)/online.inversionlabs.inversion-commander-bridge
```

Verify from Commander: `node_exec` `/usr/bin/id -u` in `/Library/CAPTNode/workspaces/main` returns
the `_captnode` uid. `cat ~/.capt/runtime.token` through `node_exec` fails with Permission denied.
**Functional change:** Commander can no longer run commands in `~/` folders. Work moves to
`/Library/CAPTNode/workspaces/*`. Each additional ACL grant is an authority expansion; list it here when made.

## 6. Retire the uid-501 Node (owner approval)

```
sudo CAPT_NODE_ACTIVATE=I-APPROVE-R04-CUTOVER bash deploy/macos/capt-node/install.sh retire-legacy
```

It refuses while the service Node is down. It disables `online.inversionlabs.capt-node-primary`
and leaves the plist in place for rollback. After this, nothing remote executes as uid 501
**through Commander's Node**. The parallel surfaces in section 9 are separate.

## 7. Post-cutover verification (record the outputs)

1. `install.sh status`: running uid = `_captnode`, socket `_captnode:captnodeclients 660`, preflight ok, legacy not running.
2. Commander manifest: `capt_node` tools present; `runtimeExec` has no `*_decide`.
3. `node_exec` probes: `id -u` → service uid; reading the human token → denied; writing `/Library/CAPTNode/trust/*` → denied.
4. `denials.jsonl` gains entries for the refused probes.
5. The R0.3 human/agent IPC behaviour still holds (`setup_split_uid_macos.sh` 13/13).

## 8. Rollback

- **Safe rollback** (Node down; Commander loses `node_exec`; no security downgrade):
  `sudo bash deploy/macos/capt-node/install.sh rollback`. This stops the daemon and kills every
  `_captnode` process (that is the revocation).
- **Downgrade rollback** (restores remote execution **as uid 501**; owner must accept explicitly):
  `sudo CAPT_NODE_ACCEPT_SAME_UID_EXPOSURE=YES bash deploy/macos/capt-node/install.sh rollback --restore-legacy`,
  then restart the bridge. This re-enables the legacy LaunchAgent and restores the newest
  `config.json.pre-r04-*`. It never happens automatically.

## 9. Not covered by this cutover (separate decisions)

These uid-501 remote surfaces run outside Commander and remain the same exposure class:
`online.inversionlabs.capt-node-integrations` (a second CAPT Node), `capt-node-perplexity-remote`
(`node_bridge`, controller `perplexity`), `capt-macos-perplexity-remote` (holds the helm token),
`capt-mcp-perplexity-remote`, `macos-control-perplexity-remote`, and `capt-actions-gateway`
behind `capt-actions-cloudflared` (public tunnel). Each needs the same treatment, or must be
disabled, before the Mac can claim no remote path to human authority.

## 10. Runtime principal (follow-up release)

The live runtime (`~/CAPT_core` e4f72d4) predates Core #253, so it has no agent principal.
Commander's `capt_runtime` plane authenticates with the **human** token. The structural fix:
upgrade the runtime past #253, issue an agent token, and point `captRuntimeArgs` at it. RuntimeService
then refuses approvals from Commander by principal, independent of edge and bridge filtering.
Upgrading the runtime is its own owner-approved release; it is not part of this package.
