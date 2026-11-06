# CAPT Node on macOS

CAPT Node is designed to run as a dedicated, unprivileged `capt` OS account. The account owns execution processes and Node state; it does not own CAPT authority.

## Security contract

- Create/use a dedicated standard macOS account named `capt`.
- Do not grant it administrator membership, sudo, Full Disk Access, Accessibility, Screen Recording, Keychain access, or blanket access to another user's home.
- Grant project access explicitly through ownership, group membership, or ACLs for each approved workspace.
- Keep Node identity/controller/authority key files mode `0600` and Node state inaccessible to unrelated users.
- The local GUI Broker described in R3-B is a separate future boundary; do not solve GUI access by weakening the `capt` account.
- A paired controller has authentication only. Every execution still requires a valid, signed, unexpired OperationCapability.

## Operator bootstrap

The repository wrapper uses the project virtualenv when present and otherwise `PYTHON`/`python3`:

```zsh
scripts/capt-node init \
  --config ~/.capt-node/node.json \
  --workspace /absolute/path/to/approved/workspace
```

`init` creates a local Unix-socket endpoint, a Node identity, and a separate capability-authority identity. Configuration and private key files are mode `0600`. `emergencyStopHotkey` is written as `null`; no default hotkey is assigned.

Pairing is a two-step human ceremony:

```zsh
scripts/capt-node pair --config ~/.capt-node/node.json --controller-id captain-runtime
# inspect verificationCode locally
scripts/capt-node pair --config ~/.capt-node/node.json --controller-id captain-runtime --approve-code <code>
```

Pairing records `executionAuthority: false`. The server independently verifies the signed OperationCapability on every execution request.

Start the local-only daemon:

```zsh
scripts/capt-node serve --config ~/.capt-node/node.json
```

Inspect node/controller state:

```zsh
scripts/capt-node status --config ~/.capt-node/node.json
scripts/capt-node controllers --config ~/.capt-node/node.json
```

Run a bounded debug operation through the Node core:

```zsh
scripts/capt-node exec \
  --config ~/.capt-node/node.json \
  --controller-id captain-runtime \
  --operation-id op-example-1 \
  --cwd /absolute/path/to/approved/workspace \
  python3 -m pytest -q
```

The CLI constructs a five-minute signed `shell.exec` capability limited to the configured workspace root containing `--cwd`. It does not expose an ambient shell session.

## Dedicated account rollout

Account creation is deliberately not automated in R3-A. A human administrator should create the standard `capt` account, provision only the required workspace ACLs, then run the daemon under that account. Verify effective UID/GID, accessible paths, denied personal paths, state-file ownership, and socket ownership before unattended use.

Do not grant GUI/TCC permissions to `capt`; R3-B will cross into the logged-in graphical session only through the approved narrow helper.

## MCP compatibility surface

CAPT Node exposes a stdio MCP adapter that consumes a pre-signed capability; it does not possess or expose a capability-authority signer.

A human operator first pairs the MCP controller and issues a bounded capability file:

```zsh
scripts/capt-node mcp-authorize \
  --config ~/.capt-node/node.json \
  --controller-id chatgpt \
  --capability-file ~/.capt-node/chatgpt.capability.json \
  --expires-minutes 60
```

Then configure the MCP client to launch:

```zsh
scripts/capt-node-mcp \
  --config ~/.capt-node/node.json \
  --controller-id chatgpt \
  --capability-file ~/.capt-node/chatgpt.capability.json
```

The MCP server exposes only `node_exec`, `node_status`, `node_evidence_read`, and `node_capability_info`. It exposes no grant/authorize/signing operation. `node_exec` uses explicit argv, remains constrained to the signed capability's filesystem roots and expiry, and is independently revalidated by CAPT Node. Large process evidence remains in the private Node evidence spool; `node_evidence_read` retrieves controller-bound chunks of at most 64 KiB using an opaque `node-evidence://` reference. Never bypass that interface by granting broad filesystem access to the spool.
