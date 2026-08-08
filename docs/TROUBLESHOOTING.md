# Troubleshooting

Start every diagnosis with:

```zsh
capt doctor
```

`capt doctor` prints a structured check list with a pass/warn/fail status and a
remediation hint for each item. Use its output plus the table below.

---

## Common failures and fixes

| Symptom | Likely cause | Fix |
|---|---|---|
| `capt: command not found` | `capt` CLI not installed on PATH | Re-run `./install.sh` from the repo, or `python3 -m pip install .`, then ensure `python3`'s bin dir is on `PATH` |
| `capt doctor` shows `env.package: fail` | package not importable | Install the package (see above); don't rely on `import` succeeding from a bare checkout |
| `capt start` times out / "not healthy" | runtime couldn't bind or start | Run `capt doctor`; check `~/.capt/start.log` (or `$CAPT_STATE_DIR/start.log`) for the service error |
| "runtime is not running" from `capt status` | service not started, or stale socket | Run `capt start` first. If a stale socket lingers, `capt start` detects and clears it |
| **range of "AF_UNIX path too long"** | default state dir path too long for a Unix socket | Set a short `CAPT_STATE_DIR`, e.g. `export CAPT_STATE_DIR=/tmp/capt` |
| Memory search returns nothing | memory stored under a different namespace | Use `--namespace` consistently; `capt memory list` shows all namespaces |
| `capt checkpoint`/`resume`/`stop` fail | runtime not running | Start it: `capt start` |
| Version mismatch between `capt --version` (0.5.0) and runtime health (0.1.0) | packaging version vs runtime-component version | Not an error; the CLI/release version and the runtime-component version are separate surfaces |
| Windows not working | unsupported platform | Windows is unverified; use macOS/Linux (see capability matrix) |

---

## Failure categories map (from the v0.6 source of truth)

| Failure | Where to look |
|---|---|
| Runtime won't start | `capt doctor`; `~/.capt/start.log` |
| Stale socket | `capt start` auto-clears; else remove `$CAPT_STATE_DIR/runtime.sock` |
| Invalid token/session | Delete `$CAPT_STATE_DIR/runtime.token` and `capt stop`/`capt start` |
| Missing driver | Model provider work is P1; see capability matrix |
| Model unavailable | Not testable until the P1 model-provider layer |
| Memory integrity error | `capt doctor` `env.package`; reinstall package |
| Checkpoint/recovery error | Ensure runtime running; check `capt doctor` |
| Approval blocked | Governed ops require approval; see USER_GUIDE Workflow B |
| Optional dependency degraded | Anti-token-extraction is optional; CAPT core continues degraded |

---

## Still stuck?

- Re-run `capt doctor` and share its full output.
- The v0.6 source of truth is `docs/V0_6_PRODUCTIZATION_SOURCE_OF_TRUTH.md`.
- The capability matrix (`docs/CAPABILITY_MATRIX.md`) tells you what is
  genuinely operator-facing versus internal/experimental, so you can tell an
  unsupported surface from a bug.