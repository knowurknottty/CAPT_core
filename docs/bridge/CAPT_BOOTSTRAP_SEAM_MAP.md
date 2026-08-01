# CAPT_BOOTSTRAP_SEAM_MAP

Evidence-only map of the two runtimes at the boundary. Every claim below was read
out of the actual source at the paths and line numbers given, on the machine that
reproduced the baseline.

---

## A. CAPT side — what already exists

### A.1 CLI surface (`capt_cli.py`, worktree `feature/capt-bootstrap-bridge`)

Discovered by reading the parser, not the workflow document. **The conceptual
command syntax in the workflow is not exact.**

| Workflow concept | Actual implementation | Status |
|---|---|---|
| `capt agent start` | `capt --json agent start --workspace WS --mission M` | exists |
| `capt agent resume` | `capt --json agent resume --workspace WS --mission M` | exists |
| `capt agent doctor` | `capt --json agent doctor` | exists |
| `capt agent status` | `capt --json agent status --workspace WS --mission M` | exists |
| `capt agent checkpoint` | **absent** — checkpointing is `capt mission checkpoint` | differs |

Two hard facts about the invocation form:

1. `--json` is a **top-level** flag, not a subcommand flag. `capt agent doctor --json`
   exits with `unrecognized arguments: --json`. The bridge must emit
   `capt --json agent …`. Verified live.
2. `args.group == "agent"` is dispatched at `capt_cli.py:373`, **before** the
   `CAPTRuntime.load()` block at :379. The agent group builds its own runtime, so
   `agent doctor` works even when other subsystems are unavailable.

Live probe of the real binary path:

```
$ capt --json agent doctor
{"ok": true, "runtime_id": "13e913775cfb4846b69613b79b02ef98",
 "single_composition_root": true,
 "provider": "no provider configured (set CAPT_MODEL_ENDPOINT and CAPT_MODEL_ID)",
 "modes": ["cave","normal","verbose","silent","audit"]}

$ capt --json agent status --workspace . --mission bootstrap-bridge-acceptance
{"execution_mode": "BLOCKED", "gate_result": "BLOCKED",
 "block_reason": "mission not found in store: bootstrap-bridge-acceptance",
 "block_codes": ["MISSION_NOT_FOUND"]}
```

CAPT **already fails closed** on an unknown mission. The bridge inherits that; it
does not need to reimplement it.

### A.2 Boot pipeline (`capt_solo/agent/boot.py`, 440 lines)

The whole governed chain the mission demands already exists inside CAPT, and the
module docstring is explicit that boot is *orchestration over canonical facilities*,
not a second implementation:

| Step | Location | Fail-closed? |
|---|---|---|
| workspace identity + git SHA/branch | `resolve_workspace` :61 | `WORKSPACE_MISSING` |
| mission resolution (explicit > session > single-active) | `resolve_mission` :76 | `MISSION_AMBIGUOUS` / `MISSION_NOT_FOUND` / `MISSION_MISSING` — never newest-wins |
| checkpoint validation (identity, digest, foreign workspace, required fields) | `validate_checkpoint` :125 | `MISSION_IDENTITY` / `CHECKPOINT_INTEGRITY` / `FOREIGN_WORKSPACE` / `CHECKPOINT_INCOMPLETE` |
| session begin/reuse | :236 | — |
| directives + supersession | `resolve_directives` :114 | — |
| Intent mint | `IntentRecord.mint` :245 | — |
| memory selection classification (selected/rejected/stale/missing/conflicting) | `runtime.gate.record_selection` :267 | — |
| ContextPack + MemoryUseGate | `runtime.gate.prepare` :273 | `execution_mode=BLOCKED` when not allowed |
| BOOTSTRAP_DEGRADED | :286-292 | requires `BOOTSTRAP_DEGRADED_AUTHORIZED` in **durable** checkpoint state, not in the request |
| boot trace persisted + hashed | `_persist_boot_trace` :396 | writes `<evidence>/agent-boot/<run>.json` + `.sha256` |
| KHSB events | `_safe_publish` :346 | `agent.boot.requested/memory_retrieved/context_validated/completed/failed` |

`AgentBootResult` already carries every field Phase 5 requires: `execution_mode`,
`mission_id`, `session_id`, `checkpoint_id`, `active_directive_ids`, `gate_result`,
and a `boot_trace` with `intent_id`, `contextpack_digest`,
`memory_use_decision_id`, `artifact_hash`.

**Conclusion: nothing in Phases 3-6 requires new governance logic. The bridge is a
launcher and a gate, not a reimplementation.**

### A.3 Provider boundary (`capt_solo/model_task.py`)

`OpenAICompatibleLocalProvider` (:178) is constructed from **environment only**
(`_agent_provider_from_env`, `capt_cli.py:407`): `CAPT_MODEL_ENDPOINT` +
`CAPT_MODEL_ID`, token via approved env var. The docstring at :410 states
credentials are never accepted as CLI args and never printed — which satisfies the
Phase 4 rule "no secrets in arguments" *by construction*, provided the bridge passes
config through env and not argv.

---

## B. Hermes side — what can actually be intercepted

### B.1 The provider call site

`agent/conversation_loop.py`:

- `:2239` `_perform_api_call(next_api_kwargs)` — the real provider call, closing over
  streaming/relay selection.
- `:2285` **every** provider invocation is routed through
  `run_llm_execution_middleware(api_kwargs, _perform_api_call, …)`.

There is exactly one such call site for the main agent loop. This is the seam.

### B.2 Middleware contract (`hermes_cli/middleware.py`)

- `:23` `LLM_EXECUTION_MIDDLEWARE = "llm_execution"`, a member of `VALID_MIDDLEWARE` :29.
- `:187` `run_llm_execution_middleware(request, next_call, **context)`; with no
  registered callbacks it degenerates to `next_call(request)` :195.
- `:254` `_run_execution_chain` gives each callback `next_call` and — decisively —
  **a callback that never calls `next_call` and returns a value suppresses the
  provider entirely.** The return value of the callback becomes the response.

`hermes_cli/plugins.py:1196` `register_middleware(kind, callback)` is public plugin
API; `llm_execution` is in `VALID_MIDDLEWARE`, so registration is warning-free.

### B.3 THE CRITICAL DEFECT IN THE SEAM — fail-open

`_run_execution_chain`, middleware.py :303-314:

```python
except Exception as exc:
    logger.warning("Middleware '%s' callback %s raised: %s", ...)
    if next_succeeded:
        return next_result
    if next_called:
        raise
    return call_at(index + 1, payload)   # <-- falls through to the PROVIDER
```

**A middleware that raises does not block the provider — Hermes swallows the
exception and calls the native provider anyway.**

This inverts the naive implementation. "Fail closed" here cannot mean "raise on
failure"; raising *is* the fail-open path. The bridge must block by **returning a
synthetic response object** and must never let an exception escape its callback.
Every blocking path in the bridge is therefore wrapped in a total try/except whose
handler still returns a blocked response.

`invoke_middleware` (plugins.py:1966-1975) has the same swallow-and-continue shape
for the request-middleware kind.

### B.4 Plugin discovery

`_discover_and_load_inner` (plugins.py:1336):

1. bundled `<repo>/plugins/` — **excluded**, that is a global Hermes mutation.
2. user `~/.hermes/plugins/` — **excluded**, global mutation.
3. project `./.hermes/plugins/` — **gated behind `HERMES_ENABLE_PROJECT_PLUGINS=1`** (:1375).
4. pip entry points, group `hermes_plugins` (:1677-1690).

Plugins are **opt-in**: `_get_enabled_plugins` (:243) returns `None` when
`plugins.enabled` is absent, and `None` means *nothing loads*. So activation
requires both the allow-list entry and, for the project path, the env flag.

Fact from the baseline environment: `capt-solo` already ships an entry point
`capt-solo = capt_solo.plugin:get_plugin` in group `hermes_plugins`. A pip-installed
CAPT is therefore *already discoverable* by Hermes without touching any global
Hermes file.

### B.5 What Hermes will NOT surrender

- Tool dispatch, the turn loop, and history remain Hermes-owned. Suppressing the
  provider does not make Hermes a pure transport at the tool layer.
- Hermes builds `api_kwargs` (system prompt, tools, history) regardless; the bridge
  discards them rather than preventing their construction.
- Subagents, summarisation, and other auxiliary call sites are separate paths from
  the main loop's :2285.

**Therefore Hermes can be made transport-only for *provider inference* — provably,
at runtime — but not transport-only for the entire agent loop.** That distinction is
recorded here and repeated in the decision record; it is the boundary of the claim
this mission may make.
