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
| Hermes workspace uses wrong npm | system npm may violate the workspace's declared engine requirement | follow the checked-out Hermes workspace's own engine/package-manager declaration; do not rely on the currently unavailable LOCAL-002 report |
| Windows failure | platform remains unverified | use a proven macOS/Linux path or produce separate Windows evidence |

## Hermes workspace note

The operator-supplied LOCAL-002 metadata stated Node `v22.22.2`, system npm `11.14.1` engine-incompatible, and npm `11.17.0` via `npx` for the faithful workspace run. Terra could not retrieve `evidence/hermes-local-002-r6`, `5c8cbf5ec1dfc0034ba7fa0931e21c88fe0cfc04`, or the report from the current GitHub remote/API. Treat those version details as **unverified historical metadata**, not as current troubleshooting authority; inspect the actual checked-out Hermes workspace requirements instead.

## Security-related failures

The active security gate is designed to remain blocked when applicable controls lack evidence. Do not work around a `BLOCKED` security verdict merely to make the stack green.

## Source of truth

Use [`CURRENT_STATE.md`](CURRENT_STATE.md), [`CAPABILITY_MATRIX.md`](CAPABILITY_MATRIX.md), and exact installed command help. The old v0.6 planning documents are historical baselines, not current operational truth.