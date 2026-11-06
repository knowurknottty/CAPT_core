# CAPT Node import provenance (R0.4)

On 2026-11-06 the service that executes Commander `node_exec` on the operator Mac ran
code that existed in no repository: `~/capt-node-assembled/capt_runtime/node/` was
**untracked** in a local clone of CAPT_core (`402f9d4b`, origin `/Users/knowurknot/CAPT_core`)
that also carried 14 uncommitted edits to tracked files.

This commit imports that Node **verbatim** so the running code and the reviewed code can
be compared byte-for-byte. Nothing is changed in this commit.

| Item | Value |
|---|---|
| Live process | PID 861, `python -m capt_runtime.node.cli serve --config ~/.capt-node/node.json`, uid 501, LaunchAgent `online.inversionlabs.capt-node-primary` |
| Source snapshot | `git ls-files --others` of `~/capt-node-assembled` (`op-r04-inventory-009`) |
| `untracked.tgz` sha256 | `f9739211aa10a25ee1da3435548ad40f11fa3f1ef78cfc6fd126bef42c2574d1` |
| `tracked.diff` sha256 (not imported) | `4edc054e6c0fbd785305eff9a32eb729e0b32bb2fb0bf000321ed0c7c918f623` |
| Node module tarball (`op-r04-inventory-005`) sha256 | `300d19ab4ddbe8710cea77906a2bc75f4ff00265fd0d8476e1d269a5e51c7fd7` |

Imported: `capt_runtime/node/*` (17 modules), `scripts/capt-node`, `scripts/capt-node-mcp`,
`docs/operations/CAPT_NODE_MACOS.md`, and 10 Node test modules.

Not imported, and why:
- `tests/capt_runtime/test_node_tool_wiring.py`, `test_node_dogfood.py`,
  `capt_runtime/tools/adapters/node_terminal.py` and the 14 tracked-file edits: they wire the
  Node into the runtime's tool broker (`create_runtime(node_client=...)`), which the live
  runtime (`~/CAPT_core` at `e4f72d4d`) does not run either. That feature needs its own review.
- Three planning/architecture notes (`docs/architecture`, `docs/evidence`, `docs/superpowers`
  `CAPT_NODE_*R3*`): historical design notes, not needed to build or run the service.

Verification: on `main` `fb0f38a9` the imported Node tests pass (51 passed before removing
the 5 wiring-dependent tests; the 10 imported modules then pass on their own).
