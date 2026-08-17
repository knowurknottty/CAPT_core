# Troubleshooting

Start with:

```zsh
capt doctor
```

Then check the exact surface you are using.

| Symptom | Likely cause | Action |
|---|---|---|
| `capt` not found | package/venv not active | activate venv; `python -m pip install -e '.[ui]'`; check `which capt` |
| `capt-ui` not found | package not installed from current repo | reinstall; check `which capt-ui` |
| TUI import says Textual missing | `ui` extra absent | `python -m pip install -e '.[ui]'` |
| `capt-ui` cannot find runtime | runtime stopped or wrong state dir | `capt start`; make `CAPT_STATE_DIR` consistent |
| Unix socket path too long | deeply nested state path | use a short `CAPT_STATE_DIR`, e.g. `/tmp/capt` |
| provider registered but generation unavailable | merged main has config/discovery but not PR #47 ProviderDriver | do not treat this as a provider credential bug; inspect current-state docs |
| provider endpoint unreachable | local service stopped/network/endpoint wrong | test provider health; verify endpoint and LOCAL/REMOTE selection |
| provider secret missing | secret reference cannot resolve | set the referenced environment/keychain secret; do not put raw secret in logs/evidence |
| context request larger than model/effective limit | requested budget exceeds provider/model/runtime policy | inspect requested vs effective context provenance in the active cockpit path |
| approval blocks run | governed action requires operator approval | approve/deny through TUI or supported runtime operation; do not bypass |
| checkpoint/resume rejected | runtime state/idempotency/recovery conflict | inspect `capt status`, evidence, and logs before retrying |
| indeterminate external execution | runtime cannot prove whether dispatch occurred | expect suspension/manual reconciliation; CAPT should not silently redispatch |
| Hermes workspace uses wrong npm | system npm may violate Hermes workspace engine requirement | use the faithful workspace npm path recorded by the Hermes evidence report |
| Windows failure | platform remains unverified | use a proven macOS/Linux path or produce separate Windows evidence |

## Hermes workspace note

The `HERMES_LOCAL_002_COMPLETE` evidence used Node `v22.22.2`; system npm `11.14.1` was engine-incompatible, while npm `11.17.0` via `npx` produced the faithful workspace run. This is an environment fidelity distinction, not a CAPT product blocker.

## Security-related failures

The active security gate is designed to remain blocked when applicable controls lack evidence. Do not work around a `BLOCKED` security verdict merely to make the stack green.

## Source of truth

Use [`CURRENT_STATE.md`](CURRENT_STATE.md), [`CAPABILITY_MATRIX.md`](CAPABILITY_MATRIX.md), and exact installed command help. The old v0.6 planning documents are historical baselines, not current operational truth.