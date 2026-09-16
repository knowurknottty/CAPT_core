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
| TUI import says Textual missing | incomplete install (current base package and `ui` extra declare Textual) | `python -m pip install -e '.[ui]'` |
| `capt-ui dashboard` exits after printing counts | this is the summary CLI, not the interactive console | use `capt tui` |
| `capt-ui` cannot find runtime | runtime stopped, wrong state dir, or stale explicit socket/token overrides | `capt start`; align `CAPT_STATE_DIR`; check `CAPT_SOCK` / `CAPT_TOKEN` (token-file path), which take precedence together; UI bootstrap also falls back to `CAPT_SOLO_HOME` when `CAPT_STATE_DIR` is unset |
| Unix socket path too long | deeply nested state path | use a short `CAPT_STATE_DIR`; a new directory selects a different runtime ledger, so retain the original state and do not treat the new runtime as recovered continuity |
| `capt memory store` succeeds but runtime context has no new memory | standalone Solo storage and runtime memory are separate | inspect `CAPT_SOLO_HOME` (default `~/.capt-solo`) versus runtime `CAPT_STATE_DIR`; `capt-ui memory --store` also writes Solo storage, so neither proves runtime admission or ContextPack inclusion |
| provider registered but generation unavailable | adapter/configuration, endpoint, model, or admission failure | merged Core includes ProviderDriver; inspect exact adapter health, model, credentials, and governed rejection before retrying |
| provider endpoint unreachable | local service stopped/network/endpoint wrong | test provider health; verify endpoint and LOCAL/REMOTE selection; health does not prove completed inference |
| provider secret missing | secret reference cannot resolve | set the referenced environment/keychain secret; do not put raw secret in logs/evidence |
| context request larger than model/effective limit | requested budget exceeds provider/model/runtime policy | inspect requested vs effective context provenance in the merged cockpit path |
| approval blocks run | governed action requires operator approval | approve/deny through TUI or supported runtime operation; do not bypass |
| checkpoint/resume rejected | runtime state/idempotency/recovery conflict | inspect `capt status`, evidence, and logs before retrying |
| indeterminate external execution | runtime cannot prove whether dispatch occurred | expect suspension/manual reconciliation; CAPT should not silently redispatch |
| Hermes workspace uses wrong npm | system npm may violate the workspace's declared engine requirement | follow the checked-out Hermes workspace's own engine/package-manager declaration; do not rely on the currently unavailable LOCAL-002 report |
| Windows failure | platform remains unverified | use a proven macOS/Linux path or produce separate Windows evidence |

## Operator control and answer display

- `E_OPERATOR_CONTROL_STALE`: refresh the control snapshot and review the effective configuration/proposal before resubmitting; do not reuse an old revision or digest.
- A model answer with `awaiting_verification` is not a completed task. Use governed provider-result review; native **Execution details** contains the receipt separately from answer text.
- A prompt proposal requiring review is not an execution failure. Review the exact original/proposed/edited basis and authority scope. Actionable research routing is included at `1e85bac`; an older installed compiler may still classify such input as underspecified.
- Missing managed skills: inspect the `managed_skills` projection or `capt skills verify --name <pack-name>` (`ultimate` is the default); use explicit import or governed install/create. Skill selection cannot grant filesystem, shell, or provider authority.

## Hermes workspace note

The operator-supplied LOCAL-002 metadata stated Node `v22.22.2`, system npm `11.14.1` engine-incompatible, and npm `11.17.0` via `npx` for the faithful workspace run. Terra could not retrieve `evidence/hermes-local-002-r6`, `5c8cbf5ec1dfc0034ba7fa0931e21c88fe0cfc04`, or the report from the current GitHub remote/API. Treat those version details as **unverified historical metadata**, not as current troubleshooting authority; inspect the actual checked-out Hermes workspace requirements instead.

## Security-related failures

The active security gate is designed to remain blocked when applicable controls lack evidence. Do not work around a `BLOCKED` security verdict merely to make the stack green.

## Source of truth

Use [`CURRENT_STATE.md`](CURRENT_STATE.md), [`CAPABILITY_MATRIX.md`](CAPABILITY_MATRIX.md), and exact installed command help. The old v0.6 planning documents are historical baselines, not current operational truth.
