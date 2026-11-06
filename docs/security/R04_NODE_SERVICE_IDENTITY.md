# R0.4 — CAPT Node service identity (architecture specification)

Status: R1 design, implemented in `capt_runtime/node/service.py`; revised per cycle (see
"Revision log"). Production cutover requires separate explicit owner approval.

## 1. Problem

The deployed CAPT Node (`online.inversionlabs.capt-node-primary`, a LaunchAgent) runs as the
human operator, uid 501. Its job is to execute processes a remote controller requests under a
signed capability (`shell.exec`). Anything uid 501 can reach, a capability holder can reach:

| Reachable by uid 501 today | Consequence through `shell.exec` |
|---|---|
| Human runtime token (`runtime.token`, 0600 uid 501) | Act as the human principal on CAPT IPC: approve, attest, dispose |
| `authority.key` next to the Node's own state | Mint capabilities for any root, any operation |
| `controller-*.key` | Impersonate a paired controller |
| Node code and the Commander bridge code (both inside the Node's workspace roots) | Rewrite the enforcement that bounds it |
| `pairings.json`, `authority.pub` (Node-owned) | Add a controller or replace the trust anchor |
| Login Keychain items (e.g. the runtime state key) | Same uid as the Keychain owner; whether a non-GUI process gets them without a prompt depends on each item's ACL — not verified, treated as reachable |

R0.3 made the *runtime* distinguish human from agent by kernel peer uid. That boundary is
worthless while a remotely driven process runs as the human uid.

## 2. Identities

| Identity | Account | Holds | May not hold |
|---|---|---|---|
| HUMAN | uid 501 `knowurknot` | human runtime token, capability authority key, controller key, operator config | — |
| HERMES AGENT | uid 502 `agent` | agent runtime token (R0.3) | human token, Node socket access |
| CAPT NODE | hidden service account `_captnode` (uid 450–499, `/usr/bin/false`, `/var/empty`, no password, not admin) | Node identity key `node.key`, journal, denials log | any of the above; write access to its own code, config or trust anchors |

Naming: macOS reserves the underscore prefix for daemon accounts; `IsHidden 1` keeps it off the
login window; a uid below 500 keeps it out of the user-account range, and `/var/empty` gives it no home.
Staging uses disposable `_captnodestg` / `captnodestgclients`.

## 3. Authority graph (revision 1)

```
HUMAN (501) ──signs──▶ capability (authority.key, operator-only)
   │                        │
   │ pairs controller       ▼
   ├──────────────▶ Commander bridge (501, mcp_stdio, controller key) ──unix socket 0660──▶ CAPT NODE (_captnode)
   │                                                                     peer uid ∈ allowedPeerUids      │
   │                                                                                                     ▼
   │                                                               shell.exec within workspaceRoots ∩ capability roots
   │
   └── runtime.token ──▶ CAPT runtime (human principal: approve / attest)   ✗ unreachable from _captnode
AGENT (502) ── agent token ──▶ CAPT runtime (agent principal)                ✗ no Node socket (not in client group)
```

Edges removed by R0.4: `_captnode → runtime.token`, `_captnode → authority.key`,
`_captnode → controller keys`, `_captnode → code/config/trust`, `agent → Node socket`,
`Node-spawned process → Node socket` (peer gate refuses the service uid itself).

## 4. Filesystem layout (production target)

| Path | Owner:group mode | Purpose |
|---|---|---|
| `/Library/CAPTNode/app` | root:wheel 0755, files 0644 | Pinned, git-archived Core commit + root-owned venv |
| `/Library/CAPTNode/etc/node.json` | root:wheel 0644 | Node config incl. `serviceIdentity` |
| `/Library/CAPTNode/trust/{authority.pub,pairings.json}` | root:wheel 0644 in 0755 dir | Trust anchors; changes are a root (owner) action |
| `/Library/CAPTNode/state` | _captnode:captnodeclients 2750 | `node.key` 0600, `journal.sqlite`, `denials.jsonl` 0640 |
| `/Library/CAPTNode/run` | _captnode:captnodeclients 0750 | `capt-node.sock` 0660 |
| `/Library/CAPTNode/workspaces/<name>` | _captnode:captnodeclients 2770 + ACL for 501 | Only places the Node may write |
| `/Library/LaunchDaemons/online.inversionlabs.capt-node.plist` | root:wheel 0644 | `UserName _captnode`, `GroupName _captnode` |
| `~/.capt-node-operator/` | 501 0700 | `authority.key`, controller key, operator config — used by the bridge |

`captnodeclients` = { 501, `_captnode` }. The service must be a member so it can chgrp the socket;
the peer gate then refuses it as a caller.

## 5. Enforcement (what the code does, not what the plist says)

Startup preflight — refuses with exit 3 and a stable code, observed by the running process about
itself: `NODE_REFUSES_ROOT`, `NODE_RUNNING_AS_FORBIDDEN_UID`, `NODE_TRUST_ANCHOR_OWNED_BY_SERVICE`,
`NODE_TRUST_ANCHOR_WRITABLE`, `NODE_TRUST_ANCHOR_MISSING`, `NODE_SIGNING_KEY_REACHABLE`,
`NODE_HUMAN_CREDENTIAL_REACHABLE`, `NODE_CODE_OR_CONFIG_WRITABLE`, `NODE_STATE_DIR_MISSING`,
`NODE_STATE_DIR_INSECURE`, `NODE_WORKSPACE_OVERLAPS_SERVICE`.

Per connection: kernel peer uid (LOCAL_PEERCRED / SO_PEERCRED) must be in `allowedPeerUids`
before a frame is read (`NODE_PEER_UID_DENIED`). Per request: controller signature, pairing,
capability authority signature (unchanged), then the capability's roots must lie inside the
deployed `workspaceRoots` (`NODE_CAPABILITY_ROOT_OUTSIDE_SERVICE_SCOPE`); then the existing
executor scope checks. Every refusal is appended to `denials.jsonl` (fsynced).

The preflight is not a sandbox. The operating system's permissions are the boundary; preflight
refuses to run when that boundary is visibly wrong. `forbiddenReadablePaths` must list the human
credentials explicitly; a credential not listed is protected by permissions alone.

## 6. Functional consequences (owner decisions)

- The Node can no longer act in `~/` workspaces. Work that needs the human's files must either
  move into `/Library/CAPTNode/workspaces/*` or be granted per-directory by ACL — each grant is an
  authority expansion and is listed in the cutover package.
- Commander planes that legitimately need human authority (runtime MCP with the human token,
  TIA, raw desktop) stay in the uid 501 bridge as fixed-function tools. They are not reachable
  through `shell.exec`. R2 examines them as laundering paths.

## 7. Revision log

- r1 (R1): identities, layout, preflight, peer gate, scope ceiling, denial log; Linux real-user
  E2E 12/12; macOS staging script.
